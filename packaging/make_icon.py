"""Generate packaging/webrtc-preview.ico (teal lab mark). Requires Pillow."""

from __future__ import annotations

from pathlib import Path


def main() -> int:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow required: pip install pillow")
        return 1

    out = Path(__file__).resolve().parent / "webrtc-preview.ico"
    sizes = [16, 32, 48, 64, 128, 256]
    images: list[Image.Image] = []
    for s in sizes:
        im = Image.new("RGBA", (s, s), (11, 16, 24, 255))
        d = ImageDraw.Draw(im)
        m = max(1, s // 16)
        # outer ring (teal)
        d.ellipse([m, m, s - 1 - m, s - 1 - m], outline=(61, 214, 198, 255), width=max(1, s // 12))
        # inner play triangle (spark)
        pad = s // 3
        d.polygon(
            [
                (pad, pad),
                (pad, s - pad),
                (s - pad, s // 2),
            ],
            fill=(240, 180, 41, 255),
        )
        images.append(im)
    # Pillow ICO: save from largest with explicit sizes list
    images[-1].save(out, format="ICO", sizes=[(im.width, im.height) for im in images])
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
