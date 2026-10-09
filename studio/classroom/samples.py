"""Read the existing private sample library, scoped to the selected entrance."""
import hashlib
import io
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2] / "Image Sample"
FOLDERS = {"colour": "Color Artwork", "sketch": "B&W Sketch"}


class SampleLibrary:
    def __init__(self, root=ROOT):
        self.root = Path(root)

    def files(self, entrance):
        folder = (self.root / FOLDERS[entrance]).resolve()
        return {
            hashlib.sha256(path.name.encode()).hexdigest()[:20]: path
            for path in sorted(folder.glob("*"))
            if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
            and path.is_file() and path.resolve().parent == folder
        }

    def image(self, entrance, sample_id, thumbnail=False):
        path = self.files(entrance)[sample_id]
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original).convert("RGB")
            image.thumbnail((320, 320) if thumbnail else (1600, 1600))
            out = io.BytesIO()
            image.save(out, format="JPEG", quality=82 if thumbnail else 94)
        return out.getvalue()
