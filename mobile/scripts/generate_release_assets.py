"""Generate committed store/release PNG assets for the citizen mobile app."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ASSETS = Path(__file__).resolve().parents[1] / "assets"

GREEN = (0, 122, 61, 255)
GREEN_DARK = (0, 92, 46, 255)
WHITE = (255, 255, 255, 255)
CREAM = (244, 246, 248, 255)
RED = (206, 17, 38, 255)


def draw_cedar(
    draw: ImageDraw.ImageDraw,
    cx: int,
    cy: int,
    size: int,
    *,
    canopy=GREEN,
    trunk=GREEN_DARK,
) -> None:
    unit = size / 32
    tiers = (
        (cy - 12 * unit, 10 * unit, 8 * unit),
        (cy - 5 * unit, 12 * unit, 9 * unit),
        (cy + 3 * unit, 14 * unit, 10 * unit),
    )
    for top, half_w, height in tiers:
        draw.polygon(
            [
                (cx, top),
                (cx - half_w, top + height),
                (cx + half_w, top + height),
            ],
            fill=canopy,
        )
    trunk_w = 3.2 * unit
    trunk_h = 8 * unit
    trunk_top = cy + 12 * unit
    draw.rectangle(
        [cx - trunk_w / 2, trunk_top, cx + trunk_w / 2, trunk_top + trunk_h],
        fill=trunk,
    )


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    icon = Image.new("RGBA", (1024, 1024), GREEN)
    draw = ImageDraw.Draw(icon)
    margin = 96
    draw.rounded_rectangle(
        [margin, margin, 1024 - margin, 1024 - margin],
        radius=180,
        fill=WHITE,
    )
    draw_cedar(draw, 512, 470, 520)
    icon.convert("RGB").save(ASSETS / "icon.png", "PNG", optimize=True)

    adaptive = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(adaptive)
    draw.ellipse([120, 120, 904, 904], fill=WHITE)
    draw_cedar(draw, 512, 470, 480)
    adaptive.save(ASSETS / "adaptive-icon.png", "PNG", optimize=True)

    splash = Image.new("RGBA", (1284, 2778), CREAM)
    draw = ImageDraw.Draw(splash)
    draw.rectangle([0, 0, 1284, 18], fill=RED)
    draw.rectangle([0, 18, 1284, 36], fill=WHITE)
    draw.rectangle([0, 36, 1284, 54], fill=RED)
    cx, cy = 642, 1200
    draw.ellipse([cx - 220, cy - 220, cx + 220, cy + 220], fill=GREEN)
    overlay = Image.new("RGBA", (1284, 2778), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    draw_cedar(overlay_draw, cx, cy - 20, 300, canopy=WHITE, trunk=(230, 245, 236, 255))
    Image.alpha_composite(splash, overlay).convert("RGB").save(
        ASSETS / "splash.png", "PNG", optimize=True
    )

    splash_icon = Image.new("RGBA", (512, 512), GREEN)
    draw = ImageDraw.Draw(splash_icon)
    draw_cedar(draw, 256, 230, 280, canopy=WHITE, trunk=(200, 230, 210, 255))
    splash_icon.convert("RGB").save(ASSETS / "splash-icon.png", "PNG", optimize=True)

    for path in sorted(ASSETS.glob("*.png")):
        print(f"{path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
