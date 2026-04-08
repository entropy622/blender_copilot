import bpy
import json
import threading
import urllib.request
import os
from . import context_manager

# 用于存储线程返回结果的临时容器
class CopilotState:
    is_processing = False
    generated_code = None
    error_message = None
    target_material_name = ""


# 全局状态实例
state = CopilotState()
def load_system_prompt(filename):
    """从 prompts 文件夹读取文本"""
    try:
        current_dir = os.path.dirname(__file__)
        file_path = os.path.join(current_dir, "prompts", filename)
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
    except Exception as e:
        print(f"Error loading prompt: {e}")
    # 备用 Prompt，防止文件读不到
    return "You are a Blender material assistant. Return Material Graph Code only."

class NODE_OT_SendPromptToLLM(bpy.types.Operator):
    bl_idname = "node.send_prompt_to_llm"
    bl_label = "Ask AI"
    bl_description = "Send prompt to AI"

    def execute(self, context):
        user_input = context.scene.copilot_prompt_text
        if not user_input.strip():
            self.report({'WARNING'}, "Prompt is empty")
            return {'CANCELLED'}

        # --- 获取用户配置 ---
        prefs = context.preferences.addons[__package__.split('.')[0]].preferences
        api_key = prefs.api_key
        api_url = prefs.api_url  # 获取自定义 URL
        model_name = prefs.model_name  # 获取自定义模型名

        if not api_key:
            self.report({'ERROR'}, "Please set API Key")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj or not obj.active_material:
            self.report({'ERROR'}, "No active object or material selected!")
            return {'CANCELLED'}
        state.target_material_name = obj.active_material.name

        # 重置状态
        state.is_processing = True
        state.generated_code = None
        state.error_message = None

        # 获取当前材质树信息
        current_tree_info = ""
        if obj.active_material and obj.active_material.node_tree:
            current_tree_info = context_manager.get_node_tree_context(obj.active_material.node_tree)
            print("Context captured:")  # 调试用
            print(current_tree_info)

        system_prompt = load_system_prompt("shader_system.txt")

        full_user_prompt = f"{current_tree_info}\n\nUSER REQUEST: {user_input}"

        # --- 启动线程 (传入新的参数) ---
        thread = threading.Thread(
            target=self.thread_function,
            args=(api_key, api_url, model_name,system_prompt, full_user_prompt)  # 传入 URL 和 Model
        )
        thread.start()

        bpy.app.timers.register(self.check_thread_result)
        return {'FINISHED'}

    # 线程函数增加参数接收
    def thread_function(self, api_key, api_url, model_name, system_prompt, prompt):
        try:
            # 强制忽略系统代理（解决国内访问 DeepSeek/OpenAI 有时被代理卡住的问题）
            import os
            os.environ['no_proxy'] = '*'

            # 如果用户只填了 https://api.deepseek.com，自动补全后缀
            if not api_url.endswith("/chat/completions"):
                # 处理末尾斜杠
                if api_url.endswith("/"):
                    api_url += "chat/completions"
                elif api_url.endswith("/v1"):
                    api_url += "/chat/completions"
                else:
                    # 尝试猜测，大部分兼容接口是 /v1/chat/completions 或者直接 /chat/completions
                    # 这里为了保险，直接补全标准的 OpenAI 格式后缀
                    api_url += "/chat/completions"

            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }

            payload = {
                "model": model_name,  # 使用配置的模型名
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "stream": False  # 确保不开启流式，方便一次性解析
            }

            print("Sending to "+api_url)

            # 使用配置的 URL
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)

            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode('utf-8'))
                state.generated_code = result['choices'][0]['message']['content']

        except Exception as e:
            state.error_message = str(e)

    # check_thread_result 函数保持不变...
    def check_thread_result(self):
        # 1. 如果还在处理，或者没有结果，继续等待
        if state.generated_code is None and state.error_message is None:
            return 0.1  # 0.1秒后再检查

        # 2. 线程结束，停止等待状态
        state.is_processing = False

        # 3. 处理错误
        if state.error_message:
            print(f"AI Error: {state.error_message}")
            self.report({'ERROR'}, f"AI Error: {state.error_message}")  # 尝试在UI报错
            return None

            # 4. 处理成功结果
        if state.generated_code:
            from . import executor
            clean_code = executor.clean_code_string(state.generated_code)

            if state.target_material_name:
                print(f"Executing Graph Code on Material: {state.target_material_name}")
                executor.execute_generated_code(clean_code, state.target_material_name)
            else:
                self.report({'ERROR'}, "Lost track of target material!")
            # -----------------------

        return None  # 停止 Timer

        return None


def register():
    bpy.utils.register_class(NODE_OT_SendPromptToLLM)


def unregister():
    bpy.utils.unregister_class(NODE_OT_SendPromptToLLM)
