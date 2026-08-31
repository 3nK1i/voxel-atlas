from pathlib import Path


ROOT = Path("prototypes/v2b3a")

required = [
    ROOT / "index.html",
    ROOT / "styles.css",
    ROOT / "app.js",
    ROOT / "assets/skull_full.glb",
]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main() -> None:
    print("===== V2B3A PROTOTYPE SMOKE =====")

    for path in required:
        require(path.is_file(), f"missing {path}")
        require(path.stat().st_size > 0, f"empty {path}")

        print(
            "PASS",
            path,
            f"({path.stat().st_size:,} bytes)",
        )

    glb = ROOT / "assets/skull_full.glb"

    with glb.open("rb") as f:
        magic = f.read(4)

    require(
        magic == b"glTF",
        "skull_full.glb does not have GLB magic",
    )

    print("PASS GLB header")

    html = (ROOT / "index.html").read_text()
    js = (ROOT / "app.js").read_text()
    css = (ROOT / "styles.css").read_text()

    checks = {
        "Three.js pinned 0.185.1":
            "three@0.185.1" in html,

        "opening slider":
            'id="openingSlider"' in html,

        "GLTF loader":
            "GLTFLoader" in js,

        "OrbitControls":
            "OrbitControls" in js,

        "dynamic shader aperture":
            "uApertureCenter" in js,

        "ellipsoid discard":
            "discard;" in js,

        "58% calibration":
            "setOpening(58)" in js,

        "prototype styling":
            ".aperture-panel" in css,
    }

    for label, ok in checks.items():
        require(ok, label)
        print("PASS", label)

    print()
    print("V2B3A_SMOKE_OK")


if __name__ == "__main__":
    main()
