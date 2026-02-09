# Image Thumbnail Specification (Pillow)

## Goal
Generate a **thumbnail derivative** suitable for embedding in an HTML “report” page, so very large uploads do not distort layout.

This specification defines an **exact, deterministic** policy for generating thumbnails using **Python + Pillow**.

---

## Thumbnail Policy Summary (normative)
- **Library:** Pillow (PIL).
- **Max dimensions:** **height ≤ 100 px** AND **width ≤ 200 px**.
- **Resizing:** **downsampling only** (never upscale).
- **Aspect ratio:** preserved during resize.
- **Cropping:** after applying the max-height rule, **crop off everything to the right of 200 px** if needed (left-anchored crop).
- **Orientation:** respect EXIF orientation (phone photos must appear upright).
- **Decompression bomb protection:** enabled (reject suspiciously large images).
- **Downsample quality:** high-quality resampling filter.
- **Post-processing:** apply a **slight sharpen** *only if* downscaling occurs.
- **Output format:** **WebP**.

---

## Inputs
Implementations SHOULD accept at least one of:
1. A filesystem path (`Path | str`) to the source image, OR
2. Source image bytes (`bytes`) plus an optional filename (for format hints), OR
3. A file-like object (`BinaryIO`) positioned at the start.

### Allowed source formats
Any format that Pillow can decode in your environment (commonly: JPEG, PNG, GIF, TIFF, BMP, WebP, etc.).

---

## Outputs
- **Primary output:** a WebP thumbnail, either written to disk or returned as `bytes` (implementation choice).
- **Output properties (MUST):**
  - Format is WebP.
  - Pixel dimensions satisfy **height ≤ 100** and **width ≤ 200**.
  - If downscaling occurred, the thumbnail is sharpened slightly.
  - If downscaling did not occur, the image is not upscaled; cropping may still occur if width > 200.
  - EXIF orientation is applied (thumbnail is visually correct).

---

## Deterministic Transform Algorithm (normative)

### Step 0 — Safety & decoding
1. Enable Pillow decompression-bomb protection:
   - Enforce a maximum decoded pixel count (`MAX_IMAGE_PIXELS`) via configuration.
   - Treat `DecompressionBombWarning` as an error.
2. Open the image with Pillow.
3. Normalize orientation:
   - Apply EXIF transpose so the image pixels match the intended orientation.

**Failure behavior (MUST):**
- If the input triggers decompression bomb protection, raise/return a clear error (e.g., `ThumbnailError`) and do not generate output.
- If Pillow cannot decode the input, raise/return a clear error.

### Step 1 — Decide whether to downscale (downsampling only)
Let `orig_w`, `orig_h` be the decoded image dimensions.

**Downscale condition:**
- If `orig_h > 100`, downscale to **target height = 100** while preserving aspect ratio.
- If `orig_h <= 100`, do **not** resize (downsampling only), proceed to cropping checks.

**Downscale math:**
- `scale = 100 / orig_h`
- `new_h = 100`
- `new_w = floor(orig_w * scale)` (or round consistently—pick one and keep it stable)

**Downscale method (MUST):**
- Use a high-quality downsampling filter (e.g., LANCZOS / equivalent).

### Step 2 — Crop width to 200 px (left-anchored)
After Step 1 (whether resized or not), let the current size be `w`, `h`.

**Cropping condition:**
- If `w > 200`, crop to width 200 by removing everything **to the right**:
  - Crop rectangle: `(left=0, top=0, right=200, bottom=h)`

**Notes:**
- This is intentionally **not** a center crop. It preserves the left side of the image.
- If `w <= 200`, do not crop.

### Step 3 — Post-processing: slight sharpening (only if downscaled)
If and only if Step 1 performed a resize (i.e., `orig_h > 100`):
- Apply a mild sharpening filter (e.g., unsharp mask) to improve perceived clarity after downsampling.

**Sharpening MUST NOT:**
- Create obvious halos or strong artifacts.
- Be applied when no resize occurred (cropping-only paths do not sharpen).

**Recommended default parameters (configurable):**
- Unsharp radius: ~1.0
- Unsharp percent: ~100
- Unsharp threshold: small (e.g., 0–3)

### Step 4 — Encode as WebP
Encode the processed image as WebP.

**Encoding policy (MUST):**
- Output format: WebP
- Preserve alpha if present (WebP supports alpha).
- Avoid unnecessary mode conversions:
  - If image has alpha, keep RGBA.
  - Otherwise, encode as RGB.

**Recommended defaults (configurable):**
- `quality`: 80 (lossy)
- `method`: 6 (slower, better compression)
- `exact`: False unless you have a reason to preserve exact RGB values
- Consider `lossless=True` only if you specifically optimize for text/screenshot fidelity over size.

---

## Configuration (suggested; implement as constants or settings)
These defaults are suggestions; expose them as parameters or settings as appropriate.

- `MAX_HEIGHT_PX = 100`
- `MAX_WIDTH_PX = 200`
- `MAX_IMAGE_PIXELS = 80_000_000` (example; choose based on your environment)
- `RESAMPLE_FILTER = LANCZOS` (or Pillow’s modern `Resampling.LANCZOS`)
- `SHARPEN_ENABLED = True`
- `SHARPEN_RADIUS = 1.0`
- `SHARPEN_PERCENT = 100`
- `SHARPEN_THRESHOLD = 3`
- `WEBP_QUALITY = 80`
- `WEBP_METHOD = 6`

---

## Edge Cases (must be handled predictably)
1. **Very tall but narrow images**: Downscale to 100px height; width may be small; no crop.
2. **Very wide panoramas**: Downscale to 100px height; width likely remains >200; crop right side to 200.
3. **Already small images (≤100px tall)**: No resize; crop only if width >200; do not sharpen.
4. **Transparency**: Preserve alpha; WebP should retain it.
5. **Animated images** (GIF/WebP):
   - Default policy: thumbnail the **first frame only** (simplest, stable). If you need animation, treat that as a separate feature.

---

## Non-goals
- No “smart” content-aware cropping (faces/objects).
- No upscaling.
- No multiple thumbnail sizes (retina 2×, etc.) in this spec.
- No caching policy specified here (implementation may cache outputs).

---

## Acceptance Criteria (tests the generator must pass)
Given any decodable image input:
1. Output is WebP.
2. Output dimensions satisfy: `height ≤ 100` and `width ≤ 200`.
3. If `orig_h > 100`, output height is exactly 100 (unless cropping reduces it—cropping must not change height).
4. If width after resize exceeds 200, output width is exactly 200 and the crop is left-anchored.
5. No output is produced for decompression-bomb-triggering inputs.
6. EXIF-rotated phone images render upright in the thumbnail.
7. Sharpening occurs only on the downscale path (not on crop-only path).

---

## Implementation Notes (non-normative hints for code generators)
- Prefer `ImageOps.exif_transpose(image)` early.
- Prefer `Resampling.LANCZOS` for downscaling.
- Consider converting `DecompressionBombWarning` into an exception via `warnings.simplefilter("error", DecompressionBombWarning)`.
- Keep behavior deterministic: choose a consistent rounding rule for `new_w`.
