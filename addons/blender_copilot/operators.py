import bpy
import json
import os
import threading
import urllib.request

from . import context_manager
from . import material_graph_store


class CopilotState:
    is_processing = False
    generated_code = None
    error_message = None
    target_material_name = ""


state = CopilotState()


def load_system_prompt(filename):
    try:
        current_dir = os.path.dirname(__file__)
        file_path = os.path.join(current_dir, "prompts", filename)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                return file.read()
    except Exception as exc:
        print(f"Error loading prompt: {exc}")
    return "You are a Blender material assistant. Return Material Graph Code only."


def _safe_report(operator, level, message):
    try:
        operator.report(level, message)
    except ReferenceError:
        print(f"Operator report skipped after reload: {message}")


class NODE_OT_SendPromptToLLM(bpy.types.Operator):
    bl_idname = "node.send_prompt_to_llm"
    bl_label = "Ask AI"
    bl_description = "Send prompt to AI"

    def execute(self, context):
        user_input = context.scene.copilot_prompt_text
        if not user_input.strip():
            _safe_report(self, {"WARNING"}, "Prompt is empty")
            return {"CANCELLED"}

        prefs = context.preferences.addons[__package__.split(".")[0]].preferences
        api_key = prefs.api_key
        api_url = prefs.api_url
        model_name = prefs.model_name

        if not api_key:
            _safe_report(self, {"ERROR"}, "Please set API Key")
            return {"CANCELLED"}

        obj = context.active_object
        if not obj or not obj.active_material:
            _safe_report(self, {"ERROR"}, "No active object or material selected!")
            return {"CANCELLED"}

        material = obj.active_material
        material_graph_store.ensure_material_graph_file(material)

        state.target_material_name = material.name
        state.is_processing = True
        state.generated_code = None
        state.error_message = None

        current_context = context_manager.get_material_context(material)
        print("Context captured:")
        print(current_context)

        system_prompt = load_system_prompt("shader_system.txt")
        full_user_prompt = f"{current_context}\n\nUSER REQUEST: {user_input}"

        thread = threading.Thread(
            target=self.thread_function,
            args=(api_key, api_url, model_name, system_prompt, full_user_prompt),
        )
        thread.start()

        bpy.app.timers.register(self.check_thread_result)
        return {"FINISHED"}

    def thread_function(self, api_key, api_url, model_name, system_prompt, prompt):
        try:
            os.environ["no_proxy"] = "*"

            if not api_url.endswith("/chat/completions"):
                if api_url.endswith("/"):
                    api_url += "chat/completions"
                elif api_url.endswith("/v1"):
                    api_url += "/chat/completions"
                else:
                    api_url += "/chat/completions"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            }

            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "stream": False,
            }

            print("Sending to " + api_url)
            req = urllib.request.Request(
                api_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
            )

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
                state.generated_code = result["choices"][0]["message"]["content"]
        except Exception as exc:
            state.error_message = str(exc)

    def check_thread_result(self):
        if state.generated_code is None and state.error_message is None:
            return 0.1

        state.is_processing = False

        if state.error_message:
            print(f"AI Error: {state.error_message}")
            _safe_report(self, {"ERROR"}, f"AI Error: {state.error_message}")
            return None

        if state.generated_code:
            from . import executor

            clean_code = executor.clean_code_string(state.generated_code)

            if state.target_material_name:
                print(f"Executing Graph Code on Material: {state.target_material_name}")
                success = executor.execute_generated_code(clean_code, state.target_material_name)
                if success:
                    material = bpy.data.materials.get(state.target_material_name)
                    if material:
                        saved_path = material_graph_store.write_material_graph(material, clean_code)
                        print(f"Saved Graph Code: {saved_path}")
                else:
                    material = bpy.data.materials.get(state.target_material_name)
                    if material:
                        draft_path = material_graph_store.write_material_graph_draft(material, clean_code)
                        print(f"Saved failed Graph Code draft: {draft_path}")
                    _safe_report(self, {"ERROR"}, "Graph Code execution failed. Script file was not updated.")
            else:
                _safe_report(self, {"ERROR"}, "Lost track of target material!")

        return None


def register():
    bpy.utils.register_class(NODE_OT_SendPromptToLLM)


def unregister():
    bpy.utils.unregister_class(NODE_OT_SendPromptToLLM)
