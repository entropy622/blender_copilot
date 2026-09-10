# 连接、升级与排错

## 直接连接

Blender Copilot 0.4 起在 Blender 进程内提供 MCP Streamable HTTP。安装 ZIP 并启用插件后即可连接，不需要另一个 Python 环境、命令行进程或服务。

在插件偏好设置中复制配置。Codex 使用 `url` 和 `http_headers`；通用 JSON 配置包含 `mcpServers`、`url` 和 `headers`，具体导入入口依客户端而定。仅支持 stdio 或旧 HTTP+SSE 的客户端不能直接连接。

默认端点为 `http://127.0.0.1:9877/mcp`。本地 token 随首次启用生成并持久保存，重启 Blender 后无需重新复制。服务不使用 OAuth，不提供浏览器登录流程。

## 从 0.3 升级

1. 禁用旧 Blender Copilot，安装新版 Release ZIP，然后重启 Blender。
2. 启用插件，在偏好设置复制新版 agent 配置。
3. 替换原来的 `[mcp_servers.blender_graph]` 配置段。移除其中的 `command`、`args`、`cwd` 和旧端口环境变量，改用 URL 配置。
4. 重新加载 agent 的 MCP 配置，调用 `blender_status`。

之前安装的外部 `blender-copilot-mcp` 和虚拟环境已不再需要。已有 Graph Code 和材质无需迁移。独立安装的其他 Blender MCP 插件与本项目无关，无需删除。

## 连接设置

- **Start / Restart MCP**：启动服务，或使用当前端口重启。
- **Stop MCP**：停止服务；禁用插件也会停止服务。
- **Copy Codex Config / Copy MCP JSON**：复制当前正在运行的端点和认证信息。
- **Reset Access Token**：重新生成本用户的 token，并重启当前服务。随后重新复制配置。其他已运行实例需重启才能采用新 token。
- **Graph Code Directory**：自定义源码保存位置。

修改端口后点击 Restart。多个 Blender 实例需要不同端口，并在 agent 中使用不同配置名称。插件遇到端口冲突时保留设置界面并显示错误，不会改用其他端口而连接到错误实例。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| Connection refused | 打开 Blender，确认插件启用且显示 MCP running |
| HTTP 401 | 重新复制配置；检查 token 是否已重置 |
| HTTP 403 | 使用插件提供的本机地址；外部网页 Origin 不允许访问 |
| GET 返回 405 | 正常：此端点通过 POST 接受 MCP 请求，不提供网页或 SSE 推送 |
| HTTP 400 / unsupported version | 使用支持 MCP Streamable HTTP 的客户端 |
| Blender 忙 / 工具超时 | 等待渲染或模态操作结束，再读取实时图确认状态 |
| revision 不匹配 | 重新读取材质后再修改 |
| 新材质没有出现在物体表面 | 创建工具追加材质槽；已有面的材质索引不会自动修改，需在 Blender 中分配 |

尚未开始执行的超时请求会被取消；已经开始的请求可能继续完成，不要直接重复提交。

## 本地文件与访问范围

状态文件位于用户目录的 `.blender-copilot/`。其中 `access-token` 保存认证 token，`bridge-<port>.json` 是运行时连接信息。服务停止会删除对应连接信息，token 保留。

连接仅监听 `127.0.0.1`。这是同一台电脑上的 agent 与 Blender 之间的连接，不支持远程云端 agent 直接访问。不要公开个人 token 或含 token 的配置。

该实现采用 MCP 2025-06-18 的无会话 JSON 响应模式，同时接受 2025-03-26；不提供 SSE 推送、资源订阅、sampling 或 OAuth。客户端可在初始化时协商协议版本。

参考：[MCP Streamable HTTP 规范](https://modelcontextprotocol.io/specification/2025-06-18/basic/transports)、[Codex MCP 配置](https://developers.openai.com/codex/mcp/)。
