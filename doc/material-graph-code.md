# Material Graph Code · Blender 5.2

Graph Code 是外部 agent 与 Blender Shader 节点图之间的 Python 风格 DSL。通过 MCP 工具提交文本，不要用普通 Python 解释器运行这些文件。

## 读写流程

`get_material_graph(material_name)` 返回：

- `graph`：实时节点、socket 默认值、属性、布局、连接。
- `code`：从实时图导出的 `Existing` 编辑脚本。
- `revision`：用于提交时检查并发修改。
- `source_code` / `source_path`：最后提交的磁盘源码及路径；没有源码时内容为 null。

`validate_graph_code` 在临时副本上执行，验证后删除副本。通过后用 `apply_graph_code` 提交 `material_name`、`code` 和 `expected_revision`。只支持 Blender 5.2.x。

## 允许的语法

允许赋值、DSL 函数调用、字符串、数值、布尔值、None、列表、元组、字典和负号。变量名不能以 `_` 开头或覆盖 DSL 函数名；节点 alias 必须唯一。

不允许 import、属性访问、bpy、函数/类定义、控制流、推导式、下标访问、参数展开及 DSL 之外的函数调用。不要包含 Markdown 代码围栏。代码大小上限为 1 MiB。

## 创建和引用节点

```python
ResetMaterial()
output = OutputMaterial()
surface = PrincipledBSDF(base_color=(0.8, 0.4, 0.2, 1.0), roughness=0.4)
Link(surface, "BSDF", output, "Surface")
```

| 函数 | 行为 |
| --- | --- |
| `ResetMaterial()` | 清空目标图；修改已有材质时要求工具参数 `allow_reset=true` |
| `Existing(name, alias=None, label=None, location=None)` | 引用已有节点；未指定布局时保留位置 |
| `Node(node_type, alias=None, name=None, label=None, location=None, **kwargs)` | 创建节点 |
| `EnsureNode(node_type, name, alias=None, label=None, location=None, **kwargs)` | 复用同名同类型节点，否则创建；类型冲突报错 |
| `OutputMaterial(...)` | 确保材质输出节点存在 |
| `PrincipledBSDF(...)` | 确保 Principled BSDF 节点存在 |

`ResetMaterial` 是整份程序的重建标记，在应用节点之前执行。不要在同一程序中混用清空后已不存在的 `Existing` 引用。

其他内置构造器默认每次创建节点：

- Shader：`DiffuseBSDF`、`GlossyBSDF`、`Emission`、`TransparentBSDF`、`MixShader`。
- 转换与颜色：`ShaderToRGB`、`ColorRamp`、`MixRGB`、`Math`、`RGB`、`Value`。
- 纹理与输入：`NoiseTexture`、`VoronoiTexture`、`TextureCoordinate`、`Mapping`。
- 辅助：`Bump`、`Fresnel`、`LayerWeight`。

重复执行包含普通创建构造器的脚本可能累积节点。更新已有图用 `Existing` 或 `EnsureNode`；重建用 `ResetMaterial`。

## Socket 和属性

```python
surface = Existing("Principled BSDF")
SetInput(surface, "Roughness", 0.6)
SetInput(surface, "Base Color", (0.2, 0.35, 0.8, 1.0))
```

socket 可以用唯一名称、identifier 或从 0 开始的整数 index。Blender 的 Math、Mix 等节点有重名 socket；重名名称会报错，须用 identifier 或 index：

```python
multiply = Math(operation="MULTIPLY")
SetInput(multiply, 0, 2.0)
SetInput(multiply, 1, 3.0)
```

`SetInput` 设置字面量时断开该输入的已有连接。传节点变量则连接其第一个输出。精确指定来源 socket 应用 `Link`：

```python
noise = NoiseTexture(scale=8.0)
surface = PrincipledBSDF()
Link(noise, "Fac", surface, "Roughness")
```

`Link(from_node, from_socket, to_node, to_socket)` 会替换目标输入的旧连接。

修改 Value、RGB 等节点的可写输出用 `SetOutput`：

```python
value = Value(value=0.5)
SetOutput(value, 0, 0.8)
color = RGB(color=(0.2, 0.3, 0.4, 1.0))
```

`SetProperty(node, property_name, value)` 设置 Blender 可写标量/数组/枚举属性。无效或不支持的属性会报错。设置影响 socket 布局的属性在默认值和连线之前执行。

```python
noise = NoiseTexture()
SetProperty(noise, "noise_dimensions", "4D")
SetInput(noise, "W", 0.3)
```

常见关键字如 `base_color`、`roughness`、`metallic`、`transmission_weight`、`specular_ior_level` 映射到 Blender 5.2 输入名。其他类型先通过 `get_node_schema` 查看当前版本，避免猜测旧版节点接口。

## 颜色渐变

```python
ramp = ColorRamp(
    stops=[
        (0.0, (0.05, 0.02, 0.01, 1.0)),
        (0.5, (0.6, 0.2, 0.05, 1.0)),
        (1.0, (1.0, 0.8, 0.4, 1.0)),
    ],
    interpolation="CONSTANT",
)
```

修改已有渐变：

```python
ramp = Existing("Color Ramp")
SetColorRamp(
    ramp,
    [(0.0, (0.0, 0.0, 0.0, 1.0)), (1.0, (1.0, 1.0, 1.0, 1.0))],
    interpolation="LINEAR",
    color_mode="RGB",
    hue_interpolation="NEAR",
)
```

`SetProperty(ramp, "interpolation", "CONSTANT")` 也支持。

## 节点组与图像

读取现有图后，直接修改节点组暴露的输入；组内部不会展开或重建：

```python
group = Existing("My Shader Group")
SetInput(group, "Roughness", 0.4)
```

从零创建时，可以引用当前 `.blend` 中已经存在的资源：

```python
group = Node("ShaderNodeGroup")
SetProperty(group, "node_tree", "MyShaderGroup")
image = Node("ShaderNodeTexImage")
SetProperty(image, "image", "albedo.png")
```

这是数据块名称，不是磁盘路径；工具不会自动下载或加载资源。

## 导出与持久化限制

实时导出的 `Existing` 脚本保留现有节点身份，可编辑默认值、属性、布局和顶层连接，也能保存颜色渐变。它依赖已有图，不是包含所有 Blender 状态的独立资产备份；节点组内部、动画/驱动、外部图像和其他复杂节点内部数据不序列化。

对于工具从零创建的材质，保留完整构造代码可重建相应节点图。仅提交局部修改时，磁盘文件记录该修改脚本；后续以实时导出为编辑起点。

应用预检失败会保留原材质和原源码，同时尝试保存 `<source>.draft.py`。文件写入使用临时文件替换；插件不自动保存 `.blend`，也不提供 Blender 操作符 Undo 入口。预检后的提交不是跨文件系统的事务，发生提交异常时应读取实时图确认状态。

源码目录和 MCP 安装方式见 [README](../README.md)。
