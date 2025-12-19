import bpy
import re


def clean_code_string(ai_response):
    pattern = r"```(?:python)?\s*(.*?)```"
    match = re.search(pattern, ai_response, re.DOTALL)
    if match:
        return match.group(1).strip()
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
        "links": active_tree.links
    }

    try:
        # 3. 执行 AI 代码
        exec(code_str, globals(), local_vars)

        # 4. 强制刷新数据
        material.node_tree.nodes.update()

        # 5. 尝试自动排版 (带上下文覆盖 + 错误保护)
        try:
            # 寻找屏幕上第一个节点编辑器窗口
            win = bpy.context.window
            scr = win.screen
            areas = [area for area in scr.areas if area.type == 'NODE_EDITOR']

            if areas:
                # 使用 temp_override 强制在节点编辑器区域执行
                with bpy.context.temp_override(window=win, area=areas[0], region=areas[0].regions[0]):
                    # 先全选节点
                    for n in active_tree.nodes:
                        n.select = True
                    # 执行排版
                    bpy.ops.node.button_layout()
            else:
                print("⚠️ Auto-layout skipped: No Node Editor found.")

        except Exception as layout_error:
            # 排版失败不应该导致整个任务失败，打印警告即可
            print(f"⚠️ Layout Warning: {layout_error}")

        return True

    except Exception as e:
        print(f"❌ Execution Error: {e}")
        import traceback
        traceback.print_exc()
        return False