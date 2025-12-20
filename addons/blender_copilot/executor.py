import bpy
import re


def clean_code_string(ai_response):
    """
    清洗 AI 回复，提取 Python 代码。
    """
    # 1. 标准模式：提取 ```python ... ``` 中间的内容
    pattern = r"```(?:python)?\s*(.*?)```"
    match = re.search(pattern, ai_response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 2. 容错模式：AI 可能忘了写 markdown，但代码里肯定有 'node_tree'
    # 如果回复里包含中文解释，直接执行会报错。
    # 我们尝试只保留代码行 (简单过滤)
    if "node_tree" in ai_response:
        print("⚠️ Warning: No markdown blocks found. Trying to filter non-code lines.")
        lines = ai_response.split('\n')
        code_lines = []
        for line in lines:
            s_line = line.strip()
            # 过滤掉明显的中文或非代码行
            if not s_line: continue
            if s_line.startswith("#"):
                code_lines.append(line)
                continue
            # 简单的特征判断：包含 = ( ) . [ ] 等符号可能是代码
            if any(c in s_line for c in "=().[]"):
                code_lines.append(line)
        return "\n".join(code_lines)

    return ai_response.strip()


def execute_generated_code(code_str, material_name):
    # 1. 获取材质
    material = bpy.data.materials.get(material_name)
    if not material:
        print(f"Error: Material '{material_name}' not found!")
        return False

    if not material.use_nodes:
        material.use_nodes = True

    active_tree = material.node_tree

    # 2. 准备沙盒环境
    local_vars = {
        "bpy": bpy,
        "node_tree": active_tree,
        "nodes": active_tree.nodes,
        "links": active_tree.links,
        # 注入一个空函数 set_val 避免 AI 如果用了以前的 Prompt 报错
        "set_val": lambda n, s, v: None
    }

    try:
        print("Executing Code:"+code_str)
        # 3. 执行 AI 代码
        exec(code_str, globals(), local_vars)

        # 4. 强制刷新数据
        material.node_tree.nodes.update()

        # 5. 尝试自动排版 (终极防崩溃版)
        try:
            target_window = None
            target_area = None
            target_region = None

            # 遍历所有窗口管理器里的窗口，而不是依赖 context.window
            for window in bpy.context.window_manager.windows:
                for area in window.screen.areas:
                    if area.type == 'NODE_EDITOR':
                        target_window = window
                        target_area = area
                        # 寻找内容区域
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                target_region = region
                                break
                        break
                if target_area: break

            if target_window and target_area and target_region:
                # 上下文覆盖
                with bpy.context.temp_override(window=target_window, area=target_area, region=target_region):
                    # 必须先选中所有节点
                    for n in active_tree.nodes:
                        n.select = True
                    bpy.ops.node.button_layout()
                    print("✅ Auto-layout applied successfully.")
            else:
                print("ℹ️ Auto-layout skipped: Node Editor not visible (background execution).")

        except Exception as layout_error:
            # 这里的报错不应该影响结果，因为 AI 已经算过坐标了
            print(f"⚠️ Layout Warning (Non-fatal): {layout_error}")

        return True

    except Exception as e:
        print(f"❌ Execution Error: {e}")
        import traceback
        traceback.print_exc()
        return False