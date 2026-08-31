# Runtime anatomy models

`skull_full.glb` is the currently qualified VoxelAtlas skull model used by the production workspace.

The V1 anatomy-layer contract reserves this exact runtime path for the brain layer:

```text
web/assets/models/brain.glb
```

The brain model must be a real, co-registered anatomical mesh in the same coordinate frame and scale as the skull. It is **not generated or substituted** by the browser when missing. Until a qualified `brain.glb` is provided, the Brain and Skull + Brain controls stay disabled instead of presenting fake anatomy.

Once a valid `brain.glb` is placed at that path, the workspace probes it at runtime and enables the Brain and Skull + Brain controls automatically.
