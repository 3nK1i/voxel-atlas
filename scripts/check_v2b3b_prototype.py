#!/usr/bin/env python3

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

HTML = ROOT / "prototypes/v2b3b/index.html"
CSS = ROOT / "prototypes/v2b3b/styles.css"
JS = ROOT / "prototypes/v2b3b/app.js"
GLB = ROOT / "prototypes/v2b3b/assets/skull_full.glb"


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def require(
    text: str,
    needle: str,
    label: str,
) -> None:

    if needle not in text:
        fail(label)


def forbid(
    text: str,
    needle: str,
    label: str,
) -> None:

    if needle in text:
        fail(label)


print(
    "===== V2B3B.7 FAST V1 SMOKE ====="
)


for path in (
    HTML,
    CSS,
    JS,
    GLB,
):

    if not path.is_file():
        fail(
            f"missing {path.relative_to(ROOT)}"
        )

    if path.stat().st_size <= 0:
        fail(
            f"empty {path.relative_to(ROOT)}"
        )

    print(
        f"PASS {path.relative_to(ROOT)} "
        f"({path.stat().st_size:,} bytes)"
    )


with GLB.open("rb") as handle:

    if handle.read(4) != b"glTF":
        fail("invalid GLB header")


print("PASS GLB header")


html = HTML.read_text()
css = CSS.read_text()
js = JS.read_text()


# VERSION

require(
    js,
    '"v2b3b-7"',
    "v2b3b-7 JS version missing",
)

require(
    html,
    "styles.css?v=v2b3b-7",
    "CSS cache version missing",
)

require(
    html,
    "app.js?v=v2b3b-7",
    "JS cache version missing",
)

print(
    "PASS version/cache contract"
)


# SINGLE MINIMAL SIDEBAR

require(
    html,
    'class="sidebar"',
    "single sidebar missing",
)

for needle in (
    "Cranial opening",
    "apertureSlider",
    "horizontalAperture",
    "verticalAperture",
):

    forbid(
        html + js,
        needle,
        f"obsolete aperture feature returned: {needle}",
    )

print(
    "PASS cranial-opening feature completely removed"
)


# SECTIONING

for needle, label in (

    (
        'data-section-axis="y"',
        "Up/Down missing",
    ),

    (
        'data-section-axis="z"',
        "Front/Back missing",
    ),

    (
        'data-section-axis="x"',
        "Left/Right missing",
    ),

    (
        'id="sectionSlider"',
        "section slider missing",
    ),

):

    require(
        html,
        needle,
        label,
    )


require(
    js,
    "renderer.localClippingEnabled",
    "local clipping disabled",
)

require(
    js,
    "updateSectionPlane",
    "section-plane implementation missing",
)

require(
    js,
    "state.sectionDepth =\n          0;",
    "orientation switch does not reset section",
)

print(
    "PASS directional sectioning contract"
)


# APPEARANCE

for needle, label in (

    (
        'data-preset="clinical"',
        "Clinical missing",
    ),

    (
        'data-preset="xr"',
        "XR missing",
    ),

    (
        'data-preset="holo"',
        "Holo missing",
    ),

    (
        'id="opacitySlider"',
        "opacity missing",
    ),

):

    require(
        html,
        needle,
        label,
    )


forbid(
    html + js,
    "Premium XR",
    "obsolete Premium XR label returned",
)

print(
    "PASS appearance contract"
)


# INTERACTION

for needle, label in (

    (
        "RIGHT:\n    THREE.MOUSE.PAN",
        "right mouse pan missing",
    ),

    (
        "LEFT:\n    THREE.MOUSE.ROTATE",
        "left mouse rotation missing",
    ),

    (
        "MIDDLE:\n    THREE.MOUSE.DOLLY",
        "middle mouse zoom missing",
    ),

    (
        "ONE:\n    THREE.TOUCH.ROTATE",
        "one-finger rotation missing",
    ),

    (
        "TWO:\n    THREE.TOUCH.DOLLY_PAN",
        "two-finger pan/zoom missing",
    ),

):

    require(
        js,
        needle,
        label,
    )


print(
    "PASS desktop + touch interaction contract"
)


# ACTIONS / AR

for needle, label in (

    (
        'id="resetButton"',
        "Reset missing",
    ),

    (
        'id="autoRotateButton"',
        "Auto rotate missing",
    ),

    (
        'id="arButton"',
        "View in AR missing",
    ),

):

    require(
        html,
        needle,
        label,
    )


require(
    js,
    'const AR_URL =',
    "AR bridge missing",
)

require(
    js,
    "https://em.eiatech.ma/",
    "validated AR destination missing",
)

print(
    "PASS actions + AR contract"
)


# RESPONSIVE

for needle, label in (

    (
        "@media (max-width: 1100px)",
        "narrow desktop breakpoint missing",
    ),

    (
        "@media (max-width: 900px)",
        "tablet/mobile breakpoint missing",
    ),

    (
        "@media (max-width: 560px)",
        "phone breakpoint missing",
    ),

    (
        "58svh",
        "mobile viewer sizing missing",
    ),

    (
        "--touch-target: 42px",
        "touch-target baseline missing",
    ),

):

    require(
        css,
        needle,
        label,
    )


require(
    js,
    "ResizeObserver",
    "responsive canvas observer missing",
)

print(
    "PASS responsive V1 contract"
)


print()
print(
    "V2B3B7_FAST_V1_SMOKE_OK"
)
