import sys
from pathlib import Path

from PIL import Image

PROMO_DIR = Path("examples/omniframe-promo").resolve()
sys.path.insert(0, str(PROMO_DIR))
from inspect_promo import build_contact_sheet  # noqa: E402


def test_contact_sheet_has_expected_grid(tmp_path: Path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    for index in range(8):
        Image.new("RGBA", (320, 180), (index * 20, 30, 80, 255)).save(
            frame_dir / f"frame_{index:06d}.png"
        )
    sheet = build_contact_sheet(frame_dir, tmp_path / "contact-sheet.png", columns=4)
    assert sheet.exists()
    assert Image.open(sheet).size == (1280, 400)
