# Material Graph Code 语法说明

本文说明 Blender Copilot 为材质蓝图生成和编辑所使用的 `Material Graph Code`。这类文件是持久化保存在磁盘上的 `.py` 文件，用来描述材质节点图；Blender 中的节点树是它编译执行后的结果。

## 1. 文件角色

- 每个材质会绑定一个 Graph Code 文件路径。
- LLM 收到的是“当前材质上下文 + 当前 Graph Code 文件内容”。
- LLM 返回的是“完整更新后的 Graph Code”，而不是局部 diff。
- 执行成功后，新代码会覆盖原文件。
- 执行失败时，会额外写出一个同路径的 `.draft.py` 草稿文件，方便排查。

## 2. 执行限制

Graph Code 看起来像 Python，但它不是任意 Python 脚本。当前执行器只允许非常有限的语法：

- 允许：赋值语句、函数调用、字面量、列表、元组、字典、负号。
- 不允许：`import`、`bpy`、函数定义、类定义、`if`、`for`、`while`、`with`、异常处理、推导式等通用 Python 语法。
- 应该输出完整文件内容，而不是只输出一小段增量补丁。

可以把它理解为“Python 风格的材质节点 DSL”。

## 3. 基本结构

一个最小可用文件通常长这样：

```python
ResetMaterial()

output = OutputMaterial()
surface = PrincipledBSDF(
    alias="surface",
    base_color=(0.8, 0.8, 0.8, 1.0),
    roughness=0.5,
)
Link(surface, "BSDF", output, "Surface")
```

含义是：

- `ResetMaterial()`：清空当前材质节点树后再重建。
- `OutputMaterial()`：确保存在材质输出节点。
- `PrincipledBSDF(...)`：创建或确保主表面节点。
- `Link(...)`：把 `BSDF` 输出连到 `Material Output.Surface`。

## 4. 顶层入口

### 4.1 材质级操作

- `ResetMaterial()`
  - 清空当前材质节点树。
  - 当用户明确要求“新建一个全新的材质”时使用。

- `Existing("Node Name", alias="...")`
  - 引用当前材质中已存在的节点。
  - 常用于在不重建整张图的情况下修改现有节点。

### 4.2 通用节点创建

- `Node(node_type, alias=None, name=None, label=None, location=None, **kwargs)`
  - 创建任意 Blender 节点。
  - `node_type` 需要是 Blender 节点类型名，例如 `ShaderNodeMath`。

- `EnsureNode(node_type, name, alias=None, label=None, location=None, **kwargs)`
  - 如果同名节点已存在则复用，否则创建。

## 5. 内置节点构造器

为了减少 LLM 输出长度，执行器内置了一批常见材质节点的简写构造器。

### 5.1 Shader 类

- `OutputMaterial(...)`
- `PrincipledBSDF(...)`
- `DiffuseBSDF(...)`
- `GlossyBSDF(...)`
- `Emission(...)`
- `TransparentBSDF(...)`
- `MixShader(...)`

### 5.2 转换与颜色类

- `ShaderToRGB(...)`
- `ColorRamp(...)`
- `MixRGB(...)`
- `Math(...)`
- `RGB(...)`
- `Value(...)`

### 5.3 纹理与输入类

- `NoiseTexture(...)`
- `VoronoiTexture(...)`
- `TextureCoordinate(...)`
- `Mapping(...)`

### 5.4 法线与辅助类

- `Bump(...)`
- `Fresnel(...)`
- `LayerWeight(...)`

这些构造器的返回值都可以继续作为变量传给 `Link(...)` 或 `SetInput(...)`。

## 6. 节点引用与变量

推荐把节点保存到变量里：

```python
noise = NoiseTexture(scale=8.0, detail=3.0, alias="noise")
ramp = ColorRamp(alias="mask", factor=noise)
surface = PrincipledBSDF(alias="surface")
SetInput(surface, "Base Color", ramp)
```

这里：

- `noise`、`ramp`、`surface` 是 Graph Code 层面的变量。
- `alias` 是节点在 Graph Code 内部的稳定标识，方便后续连接和修改。
- `name` 是 Blender 节点树里显示的节点名。

## 7. 参数规则

大多数构造器都接受两类参数：

- 节点输入参数：例如 `base_color`、`roughness`、`factor`、`strength`
- 节点属性参数：例如 `ColorRamp(interpolation="CONSTANT")`、`MixRGB(blend_type="MULTIPLY")`

执行器会尝试把关键字参数映射到对应输入 socket 或节点属性。

### 7.1 常见值类型

- 浮点数：`0.6`
- 颜色：`(0.8, 0.4, 0.2, 1.0)`
- 向量：`(0.0, 0.0, 1.0)`
- 节点引用：`factor=noise`、`height=noise`

如果某个参数传入的是另一个节点变量，执行器会自动尝试把这个节点的合适输出连过去。

## 8. 连接与修改

### 8.1 Link

```python
Link(surface, "BSDF", output, "Surface")
Link(noise, "Fac", ramp, "Fac")
```

显式创建一条节点连线。

### 8.2 SetInput

```python
SetInput(surface, "Base Color", (0.9, 0.7, 0.5, 1.0))
SetInput(surface, "Roughness", 0.8)
SetInput(surface, "Normal", bump)
```

用于修改一个节点的输入。第三个参数既可以是：

- 直接值
- 颜色/向量
- 另一个节点变量

### 8.3 SetProperty

```python
SetProperty(ramp, "interpolation", "CONSTANT")
SetProperty(mix, "blend_type", "MULTIPLY")
```

用于修改节点本身的属性，而不是输入 socket。

## 9. Blender 4.x 命名兼容

`Principled BSDF` 在 Blender 4.x 有一些输入名和旧版本不同。建议优先使用 Blender 4.x 名称：

- `Subsurface Weight`
- `Transmission Weight`
- `Coat Weight`
- `Sheen Weight`
- `Specular IOR Level`
- `Emission Color`

当前执行器也兼容一部分旧名，例如：

- `Subsurface` -> `Subsurface Weight`
- `Transmission` -> `Transmission Weight`
- `Coat` -> `Coat Weight`
- `Sheen` -> `Sheen Weight`
- `Specular` -> `Specular IOR Level`
- `Emission` -> `Emission Color`

但文档和新代码应尽量直接使用新名称或对应的 snake_case 关键字，例如：

- `subsurface_weight=0.0`
- `transmission_weight=0.0`
- `coat_weight=0.0`
- `specular_ior_level=0.5`

## 10. 示例

### 10.1 重新生成一个基础 PBR 材质

```python
ResetMaterial()

output = OutputMaterial()
surface = PrincipledBSDF(
    alias="surface",
    base_color=(0.45, 0.35, 0.25, 1.0),
    metallic=0.0,
    roughness=0.75,
    specular_ior_level=0.5,
)
Link(surface, "BSDF", output, "Surface")
```

### 10.2 生成一个简单的 toon 材质

```python
ResetMaterial()

output = OutputMaterial()
diffuse = DiffuseBSDF(color=(0.85, 0.35, 0.25, 1.0), roughness=1.0, alias="diffuse")
to_rgb = ShaderToRGB(shader=diffuse, alias="to_rgb")
ramp = ColorRamp(
    alias="toon_ramp",
    factor=to_rgb,
    interpolation="CONSTANT",
    stops=[
        (0.0, (0.15, 0.05, 0.03, 1.0)),
        (0.45, (0.15, 0.05, 0.03, 1.0)),
        (0.46, (0.95, 0.55, 0.35, 1.0)),
        (1.0, (0.95, 0.55, 0.35, 1.0)),
    ],
)
surface = Emission(color=ramp, strength=1.0, alias="surface")
Link(surface, "Emission", output, "Surface")
```

### 10.3 修改现有节点

```python
surface = Existing("Principled BSDF", alias="surface")

SetInput(surface, "Base Color", (0.2, 0.35, 0.8, 1.0))
SetInput(surface, "Roughness", 0.25)
SetInput(surface, "Metallic", 0.9)
```

## 11. 编写建议

- 需要重建整张图时再使用 `ResetMaterial()`。
- 只修改现有图时，优先使用 `Existing(...)`。
- 优先使用内置构造器，不要直接写 `bpy`。
- 每次返回完整文件内容，避免只返回片段。
- 尽量保证最终有一条有效链路连到 `Material Output.Surface`。
