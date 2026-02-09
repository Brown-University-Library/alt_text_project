"""
Helpers for generating image thumbnails.
"""

import io
import math
import warnings
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError

THUMBNAIL_MAX_HEIGHT_PX = 100
THUMBNAIL_MAX_WIDTH_PX = 200
THUMBNAIL_MAX_IMAGE_PIXELS = 80_000_000
THUMBNAIL_WEBP_QUALITY = 80
THUMBNAIL_WEBP_METHOD = 6
THUMBNAIL_SHARPEN_RADIUS = 1.0
THUMBNAIL_SHARPEN_PERCENT = 100
THUMBNAIL_SHARPEN_THRESHOLD = 3


class ThumbnailError(Exception):
    """
    Represents failures during thumbnail generation.
    """


def generate_thumbnail_webp(image_path: Path) -> tuple[bytes, int, int]:
    """
    Generates a deterministic WebP thumbnail for the supplied image path.
    """
    thumbnail_bytes: bytes = b''
    width_px = 0
    height_px = 0
    Image.MAX_IMAGE_PIXELS = THUMBNAIL_MAX_IMAGE_PIXELS
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(image_path) as image:
                if getattr(image, 'is_animated', False):
                    image.seek(0)
                image = ImageOps.exif_transpose(image)
                original_width, original_height = image.size
                resized = False
                if original_height > THUMBNAIL_MAX_HEIGHT_PX:
                    scale = THUMBNAIL_MAX_HEIGHT_PX / original_height
                    new_width = math.floor(original_width * scale)
                    new_height = THUMBNAIL_MAX_HEIGHT_PX
                    working = image.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)
                    resized = True
                else:
                    working = image.copy()
                if working.width > THUMBNAIL_MAX_WIDTH_PX:
                    working = working.crop((0, 0, THUMBNAIL_MAX_WIDTH_PX, working.height))
                if resized:
                    working = working.filter(
                        ImageFilter.UnsharpMask(
                            radius=THUMBNAIL_SHARPEN_RADIUS,
                            percent=THUMBNAIL_SHARPEN_PERCENT,
                            threshold=THUMBNAIL_SHARPEN_THRESHOLD,
                        )
                    )
                has_alpha = working.mode in ('RGBA', 'LA') or (
                    working.mode == 'P' and 'transparency' in working.info
                )
                if has_alpha:
                    working = working.convert('RGBA')
                else:
                    working = working.convert('RGB')
                width_px, height_px = working.size
                output = io.BytesIO()
                working.save(
                    output,
                    format='WEBP',
                    quality=THUMBNAIL_WEBP_QUALITY,
                    method=THUMBNAIL_WEBP_METHOD,
                )
                thumbnail_bytes = output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning, UnidentifiedImageError) as exc:
        raise ThumbnailError(str(exc)) from exc
    except OSError as exc:
        raise ThumbnailError(str(exc)) from exc
    return thumbnail_bytes, width_px, height_px
