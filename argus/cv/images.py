"""Image helpers shared by the vision nodes."""
import base64
from io import BytesIO

from PIL import Image

from argus import config


def downscaled_b64(path: str) -> str:
    """JPEG-downscale a screenshot for the VLM — layout bugs survive, token cost doesn't."""
    img = Image.open(path)
    if img.width > config.VLM_IMAGE_WIDTH:
        img = img.resize(
            (config.VLM_IMAGE_WIDTH, int(img.height * config.VLM_IMAGE_WIDTH / img.width)))
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()
