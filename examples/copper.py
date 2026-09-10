# Graph Code DSL; send this text to create_material or apply_graph_code.
ResetMaterial()
output = OutputMaterial()
noise = NoiseTexture(scale=7.0, detail=4.0, roughness=0.65)
color = ColorRamp(
    stops=[
        (0.25, (0.09, 0.025, 0.008, 1.0)),
        (0.75, (0.65, 0.27, 0.10, 1.0)),
    ],
)
bump = Bump(strength=0.15, distance=0.05)
surface = PrincipledBSDF(metallic=0.95, roughness=0.32)
Link(noise, "Fac", color, "Fac")
Link(noise, "Fac", bump, "Height")
Link(color, "Color", surface, "Base Color")
Link(bump, "Normal", surface, "Normal")
Link(surface, "BSDF", output, "Surface")
