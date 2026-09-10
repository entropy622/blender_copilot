"""Dependency-free, stateless MCP Streamable HTTP endpoint.

Supports the JSON response mode of the 2025-06-18 transport specification.
No SSE, sessions, sampling, resources or prompts are advertised.
All Blender calls run on the main-thread queue, never HTTP worker threads.
"""
from concurrent.futures import Future, TimeoutError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import json
import os
from pathlib import Path
import queue
import secrets
import threading

import bpy

MAX_MESSAGE = 4 * 1024 * 1024
VERSIONS = ("2025-03-26", "2025-06-18")
_server = None
_thread = None
_pending = queue.Queue(maxsize=32)
last_error = ""


def state_directory():
    return Path(os.environ.get("BLENDER_COPILOT_STATE_DIR", str(Path.home() / ".blender-copilot")))


def port():
    addon = bpy.context.preferences.addons.get(__package__)
    default = addon.preferences.mcp_port if addon else 9877
    return int(os.environ.get("BLENDER_COPILOT_PORT", str(default)))


def connection_path():
    return state_directory() / f"bridge-{port()}.json"


def token(reset=False):
    path = state_directory() / "access-token"
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset:
        path.unlink(missing_ok=True)
    if not path.exists():
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
    value = path.read_text(encoding="utf-8").strip()
    if not value:
        raise RuntimeError("Empty MCP token file; reset the token in add-on preferences.")
    return value


def address():
    actual_port = _server.server_port if _server else port()
    return f"http://127.0.0.1:{actual_port}/mcp"


def config(kind):
    if not _server:
        raise RuntimeError(last_error or "MCP server is stopped. Start it first.")
    authorization = "Bearer " + _server.token
    if kind == "CODEX":
        return ('[mcp_servers.blender_graph]\nurl = ' + json.dumps(address())
            + '\nhttp_headers = { Authorization = ' + json.dumps(authorization)
            + ' }\ntool_timeout_sec = 45\n')
    return json.dumps({"mcpServers": {"blender_graph": {
        "url": address(), "headers": {"Authorization": authorization}}}}, indent=2)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(35)

    def log_message(self, format, *args):
        # Never log HTTP headers or the access token.
        pass

    def send(self, status, payload=None):
        data = b"" if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        if len(data) > MAX_MESSAGE:
            status, data = 500, b'{"error":"Response exceeds 4 MiB"}'
        self.send_response(status)
        if payload is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        if status == 405:
            self.send_header("Allow", "POST")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(data)
        except OSError:
            pass

    def guard(self):
        if self.path != "/mcp":
            self.send(404)
            return False
        allowed_hosts = {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}
        if self.headers.get("Host") not in allowed_hosts:
            self.send(403)
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {"http://" + host for host in allowed_hosts}:
            self.send(403)
            return False
        if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), ("Bearer " + self.server.token).encode()):
            self.send(401)
            return False
        if self.headers.get("MCP-Protocol-Version", "2025-03-26") not in VERSIONS:
            self.send(400, {"error": "Unsupported MCP-Protocol-Version"})
            return False
        return True

    def do_GET(self):
        if self.guard():
            self.send(405)

    def do_DELETE(self):
        if self.guard():
            self.send(405)

    def do_POST(self):
        if not self.guard():
            return
        if self.headers.get_content_type() != "application/json":
            self.send(415)
            return
        accept = self.headers.get("Accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            self.send(406)
            return
        if self.headers.get("Transfer-Encoding"):
            self.send(400)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > MAX_MESSAGE:
                self.send(413)
                return
            raw = self.rfile.read(size)
            request = json.loads(raw)
        except (ValueError, OSError):
            self.send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Invalid JSON"}})
            return
        request_id = request.get("id") if isinstance(request, dict) else None
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0" or not isinstance(request.get("method"), str) or ("id" in request and (isinstance(request_id, bool) or not isinstance(request_id, (str, int)))):
            self.send(400, {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid JSON-RPC request"}})
            return
        # Notifications must not trigger tools or scene mutations.
        if "id" not in request:
            self.send(202)
            return
        method, params = request["method"], request.get("params", {})
        if not isinstance(params, dict):
            self.rpc_error(request_id, -32602, "params must be an object")
            return
        if method == "initialize":
            requested = params.get("protocolVersion")
            result = {"protocolVersion": requested if requested in VERSIONS else VERSIONS[-1],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "Blender Graph Code", "version": "0.4.0"},
                "instructions": "Use Graph Code DSL, never bpy. Read live graph and node schemas, validate, then apply using expected_revision. Existing exports need the original nodes. ResetMaterial requires allow_reset=true."}
        elif method == "ping":
            result = {}
        elif method == "tools/list":
            result = {"tools": self.server.schemas}
        elif method == "tools/call":
            name, arguments = params.get("name"), params.get("arguments", {})
            schema = self.server.by_name.get(name) if isinstance(name, str) else None
            if schema is None:
                self.rpc_error(request_id, -32602, "Unknown tool")
                return
            from .mcp_tools import validate_arguments
            try:
                validate_arguments(schema, arguments)
            except ValueError as exc:
                self.rpc_error(request_id, -32602, str(exc))
                return
            future = Future()
            try:
                self.server.pending.put_nowait(({"tool": "status" if name == "blender_status" else name, "arguments": arguments}, future))
                try:
                    value = future.result(timeout=30)
                except TimeoutError:
                    cancelled = future.cancel()
                    raise RuntimeError("Blender is busy; request cancelled before execution." if cancelled else "Execution started but timed out. Read the graph before retrying.")
                result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, allow_nan=False)}], "isError": False}
            except Exception as exc:
                message = "Blender request queue is full." if isinstance(exc, queue.Full) else str(exc)
                result = {"content": [{"type": "text", "text": message}], "isError": True}
        else:
            self.rpc_error(request_id, -32601, "Method not found")
            return
        self.send(200, {"jsonrpc": "2.0", "id": request_id, "result": result})

    def rpc_error(self, request_id, code, message):
        self.send(200, {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False
    allow_reuse_address = False


def drain():
    from .tool_api import dispatch
    for _ in range(8):
        try:
            request, future = _pending.get_nowait()
        except queue.Empty:
            break
        if not future.set_running_or_notify_cancel():
            continue
        try:
            future.set_result(dispatch(request.get("tool"), request.get("arguments", {})))
        except Exception as exc:
            future.set_exception(exc)
    return 0.05


def start():
    global _server, _thread, last_error, _pending
    if _server:
        return
    from .mcp_tools import schemas
    server = None
    try:
        server = Server(("127.0.0.1", port()), Handler)
        server.token = token()
        server.schemas = schemas()
        server.by_name = {s["name"]: s for s in server.schemas}
        _pending = queue.Queue(maxsize=32)
        server.pending = _pending
        path = connection_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        server.connection_file = path
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps({"url": f"http://127.0.0.1:{server.server_port}/mcp", "token": server.token, "pid": os.getpid()}), encoding="utf-8")
        temp.chmod(0o600)
        temp.replace(path)
        bpy.app.timers.register(drain, persistent=True)
        _thread = threading.Thread(target=server.serve_forever, daemon=True, name="GraphCodeMCP")
        _thread.start()
        _server = server
        last_error = ""
    except Exception as exc:
        last_error = str(exc)
        if server:
            server.server_close()
        if bpy.app.timers.is_registered(drain):
            bpy.app.timers.unregister(drain)
        raise


def stop():
    global _server, _thread
    if _server:
        _server.shutdown()
        _server.server_close()
        if _thread:
            _thread.join(timeout=2)
        path = _server.connection_file
        try:
            if json.loads(path.read_text(encoding="utf-8")).get("pid") == os.getpid():
                path.unlink()
        except (OSError, ValueError):
            pass
        _server = _thread = None
    if bpy.app.timers.is_registered(drain):
        bpy.app.timers.unregister(drain)
    while not _pending.empty():
        _, future = _pending.get_nowait()
        future.cancel()
