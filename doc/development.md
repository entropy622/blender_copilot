# 开发、测试与发布

普通用户只需安装 Release ZIP。以下步骤仅用于贡献代码或运行测试。

## 结构

```text
addons/blender_copilot/
  bridge.py                插件内置 HTTP MCP、认证、主线程队列
  mcp_tools.py             工具发现与参数 schema
  tool_api.py              Blender 工具操作
  executor.py              Graph Code 编译与执行
  graph_snapshot.py        实时图读取与编辑脚本导出
  material_graph_store.py  源码存储
  preferences.py           服务状态与配置复制
examples/                  Graph Code 示例
scripts/package_addon.py   Release ZIP 打包
tests/                     Blender 集成测试、标准 MCP 客户端测试
```

插件运行只依赖 Blender 自带的 Python 标准库。MCP SDK 和 httpx 仅用于开发测试，不进入 Release ZIP。

## 测试环境

Python 3.11+，以及可用的 Blender 5.2.x。将 Blender 可执行文件加入 PATH，或通过 `BLENDER_EXECUTABLE` 指定。

```sh
python -m venv .venv
# 激活虚拟环境后：
python -m pip install -e ".[test]"
python scripts/package_addon.py
blender --background --factory-startup --python-exit-code 1 --python tests/blender_integration.py
python -m unittest discover -s tests -p test_mcp_integration.py -v
```

Windows 的可执行文件名是 `blender.exe`。测试不会操作正在编辑的场景：使用独立后台进程、临时目录及 19878/19879 端口。

HTTP 集成测试从 Release ZIP 解压插件，使用标准 MCP SDK 直接连接它，验证初始化、7 个工具、认证、Origin、错误响应、材质修改、revision 检查和重启重连。Graph Code 测试覆盖回放、节点组、重复 socket、无效代码、取消请求与 Cycles 渲染。

`scripts/test_live_material.py` 是人工演示脚本，会连接个人 Codex 配置中的 `blender_graph` 并创建材质；需要预先存在名为 `GraphCode_Patina_Sphere` 的对象。`--verify-only` 只回读已有演示材质。它不属于隔离测试。

## 打包与发布

```sh
python scripts/package_addon.py
```

版本取自插件 `bl_info`，输出 `dist/blender_copilot-<version>.zip`。ZIP 包含插件代码和许可证，不包含缓存、测试、图片、个人配置或第三方运行时。

发布工作流在版本 tag 上生成安装包并创建 GitHub draft release；维护者检查发布说明和附件后再公开。手动运行工作流只构建上传 artifact。对外支持平台以 README 中经过验证的列表为准。

## 线程和协议约定

HTTP 工作线程只处理协议、认证和队列。所有 Blender 数据访问通过主线程定时器执行；不要在请求处理函数中调用 bpy。

MCP 采用 Streamable HTTP 的无会话 JSON 响应模式。GET/DELETE 返回 405，通知返回 202，不广告尚未实现的能力。端口被占用时显示错误并允许用户从偏好设置重试。

## 执行边界

预检能在修改原图之前发现通常的 DSL 和 Blender API 错误，但提交不是跨文件系统的事务。预检后的进程崩溃等异常仍可能造成状态不一致；保持错误信息可诊断，让 agent 重新读取图。
