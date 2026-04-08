ResetMaterial()

# Create a realistic skin material with subsurface scattering, subtle roughness, and natural color variation

output = OutputMaterial()
principled = PrincipledBSDF(
    alias="principled",
    base_color=(0.85, 0.65, 0.45, 1.0),
    roughness=0.35,
    subsurface_weight=0.25,
    subsurface_radius=(1.0, 0.7, 0.5),
    metallic=0.0,
    transmission_weight=0.0,
    coat_weight=0.0,
    sheen_weight=0.0,
    specular_ior_level=0.5,
    emission_color=(0.0, 0.0, 0.0, 1.0),
    emission_strength=0.0
)

# Add subtle noise for skin texture
noise = NoiseTexture(scale=10.0, detail=5.0, roughness=0.7, distortion=2.0)
color_ramp = ColorRamp(
    alias="skin_noise",
    factor=noise,
    interpolation="SMOOTH",
    stops=[
        (0.0, (0.8, 0.6, 0.4, 1.0)),
        (0.5, (0.85, 0.68, 0.48, 1.0)),
        (1.0, (0.9, 0.7, 0.5, 1.0))
    ]
)

# Modulate base color with noise
mix_rgb = MixRGB(
    blend_type="MULTIPLY",
    factor=0.3,
    color1=(0.85, 0.65, 0.45, 1.0),
    color2=color_ramp
)

SetInput(principled, "Base Color", mix_rgb)

Link(principled, "BSDF", output, "Surface")
