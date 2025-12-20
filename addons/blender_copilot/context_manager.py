import bpy


def get_node_tree_context(node_tree):
    """
    将节点树序列化为 LLM 易读的文本描述。
    包含：节点列表、关键参数值、连接关系。
    """
    if not node_tree:
        return "No active node tree."

    info = []
    info.append(f"--- CURRENT NODE TREE STATE ({node_tree.name}) ---")

    # 1. 记录现有节点 (Nodes)
    info.append("EXISTING NODES:")
    node_map = {}  # 用来存名字和类型的映射

    for node in node_tree.nodes:
        # 记录节点的基本信息
        # 格式: Name: "Material Output" (Type: ShaderNodeOutputMaterial) at (300, 0)
        node_desc = f'- Name: "{node.name}" (Type: {node.bl_idname}, Location: ({int(node.location.x)}, {int(node.location.y)}))'
        info.append(node_desc)

        # 记录节点的关键输入值 (Inputs)
        # 只记录没有被连线(is_linked=False)且有值的端口
        input_values = []
        for socket in node.inputs:
            if not socket.is_linked and hasattr(socket, "default_value"):
                val = socket.default_value
                # 格式化数值，避免由浮点数精度导致的超长小数
                val_str = ""
                try:
                    if isinstance(val, float):
                        val_str = f"{val:.3f}"
                    elif hasattr(val, "__len__") and len(val) <= 4:  # Vector/Color
                        val_str = f"({', '.join([f'{v:.3f}' for v in val])})"
                    else:
                        val_str = str(val)

                    if val_str:
                        input_values.append(f'  - "{socket.name}": {val_str}')
                except:
                    pass

        if input_values:
            info.append("  Properties:")
            info.extend(input_values)

    # 2. 记录连接关系 (Links)
    info.append("\nEXISTING LINKS:")
    if not node_tree.links:
        info.append("- No links.")
    else:
        for link in node_tree.links:
            # 格式: "Principled BSDF".BSDF -> "Material Output".Surface
            link_desc = f'- "{link.from_node.name}".{link.from_socket.name} -> "{link.to_node.name}".{link.to_socket.name}'
            info.append(link_desc)

    info.append("--- END OF CURRENT STATE ---")

    return "\n".join(info)