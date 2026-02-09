# PLAN — Store & Serve DB Thumbnail on Report Page

## Goal
Change the report-page image preview so it displays a **thumbnail stored in the database** (not a proxied stream of the original uploaded file), because original files may be auto-deleted over time.

The thumbnail generation must follow `alt_text_project/image_thumbnail_specification.md` (Pillow → deterministic WebP, max height 100, max width 200 with left-anchored crop, EXIF transpose, decompression-bomb protection, sharpen only when downscaling).

---

## Current Behavior (as of Feb 9, 2026)
- **Template**: `alt_text_app/alt_text_app_templates/alt_text_app/report.html` uses:
  - `<img src="{% url 'image_preview_url' pk=document.pk %}" ... />`
- **URL**: `alt_text_project/config/urls.py`
  - `path('image/preview/<uuid:pk>/', views.image_preview, name='image_preview_url')`
- **View**: `alt_text_app/views.py::image_preview()`
  - Locates file on disk via `image_helpers.get_image_path(checksum, extension)`
  - Streams original bytes via `FileResponse(open(image_path, 'rb'), content_type=doc.mime_type)`
- **Original storage**: `alt_text_app/lib/image_helpers.py::save_image_file()` writes to `settings.IMAGE_UPLOAD_PATH` on disk.

Implication:
- If the disk file is deleted later, the report page will 404 its preview.

---

## Proposed Design
### Data model (DB persistence)
Add fields on `alt_text_app.models.ImageDocument` to store the thumbnail payload and minimal metadata.

Recommended minimal fields:
- `thumbnail_webp` (BinaryField, nullable): the generated WebP bytes.
- `thumbnail_created_at` (DateTimeField, nullable): when thumbnail was created.
- `thumbnail_error` (TextField, nullable): last failure reason, if generation fails.

Optional (only if you want extra introspection / debugging):
- `thumbnail_width_px`, `thumbnail_height_px` (IntegerField, nullable)

Notes:
- Content type can be assumed `image/webp` (per spec), so a dedicated `thumbnail_mime_type` field is not required.

### Thumbnail generation placement (architecture)
Follow `AGENTS.md` Django conventions:
- Keep `views.py` as orchestration only.
- Put thumbnail generation logic in `alt_text_app/lib/` as pure, testable functions.

Create a new module (planned):
- `alt_text_app/lib/thumbnail_helpers.py`

Planned primary API (pure function returning bytes):
- Input: at least `Path` to the original image (matches existing workflow: upload saves file to disk and returns `Path`).
- Output: WebP bytes + (optionally) width/height.

### When the thumbnail is created
Create the thumbnail **immediately after successfully saving the uploaded file** in `views.upload_image()`.

Why:
- This guarantees the thumbnail exists before any downstream cleanup deletes originals.
- Avoids “lazy generation” failing later due to missing originals.

### How the report preview is served
Change `views.image_preview()` to:
- Fetch `ImageDocument`.
- If `doc.thumbnail_webp` exists:
  - Return `HttpResponse(doc.thumbnail_webp, content_type='image/webp')`.
- If it does not exist:
  - Return a 404 (or a small HTML response) **without** streaming the original.

(This satisfies “don’t proxy the original.”)

---

## Thumbnail Algorithm Requirements (from spec)
Implementation in `thumbnail_helpers` should:
- **Orientation**: apply EXIF transpose (upright phone photos).
- **Decompression bomb protection**:
  - enforce `MAX_IMAGE_PIXELS` (configurable)
  - treat `DecompressionBombWarning` as error
- **Resize policy**:
  - downsample only (never upscale)
  - if `orig_h > 100`: resize to height 100, preserve aspect ratio, stable rounding for width
  - use high-quality resampler (LANCZOS)
- **Crop policy**:
  - if width after resize (or original width if no resize) exceeds 200: crop right side
  - crop rectangle `(0, 0, 200, h)`
- **Sharpening**:
  - apply mild sharpen only if the downscale path occurred
- **Output**: WebP, preserve alpha

---

## Dependencies / Settings
### Add Pillow
~~Project dependencies are managed via `uv` and `pyproject.toml` (`alt_text_project/pyproject.toml`). Pillow is not currently listed~~. Done; I've added it.

Plan:
- ~~Add Pillow to dependencies (example constraint: `Pillow~=10.0` or whatever matches your environment policy).~~
- ~~Update lockfile (`uv.lock`).~~
- Done; I've added it.

### Thumbnail-related settings 
I do _not_ want these to be configurable, so they will not be added to django settings. Instead add these in `thumbnail_helpers` as module-level constants:
- `THUMBNAIL_MAX_HEIGHT_PX = 100`
- `THUMBNAIL_MAX_WIDTH_PX = 200`
- `THUMBNAIL_MAX_IMAGE_PIXELS = ...`
- `THUMBNAIL_WEBP_QUALITY = 80`
- `THUMBNAIL_WEBP_METHOD = 6`
- `THUMBNAIL_SHARPEN_RADIUS = 1.0`
- `THUMBNAIL_SHARPEN_PERCENT = 100`
- `THUMBNAIL_SHARPEN_THRESHOLD = 3`

---

## Migration Plan
1. Update `ImageDocument` model fields (add thumbnail fields).
2. Create migration.
3. Apply migration.

### Commands you will run
From project root (per `AGENTS.md`, use `uv run`):
- `uv run ./manage.py makemigrations alt_text_app`
- `uv run ./manage.py migrate`

---

## Implementation Milestones (recommended order)
1. **Model support**
   - Add DB fields on `ImageDocument` to store the thumbnail.
   - Add migration.

2. **Thumbnail generator module** (`alt_text_app/lib/thumbnail_helpers.py`)
   - Implement deterministic spec-compliant thumbnail creation.
   - Raise a clear exception type on failure (ex: `ThumbnailError`).
   - Ensure decompression-bomb protection behavior is deterministic.

3. **Write path integration** (`views.upload_image()`)
   - After `image_helpers.save_image_file()` succeeds, generate thumbnail from the saved path.
   - Save thumbnail bytes to the `ImageDocument` row.
   - Failure policy:
     - If thumbnail generation fails: record `thumbnail_error`, but do not fail the whole upload (unless you decide thumbnail is mandatory).

4. **Read path integration** (`views.image_preview()`)
   - Serve thumbnail bytes from DB.
   - Do not read from disk.

5. **Backfill strategy for existing rows**
   - Add a one-off script or management command to generate thumbnails for historical documents that still have originals on disk.
   - This is especially useful if you already have rows in production.

---

## Testing Plan
Add focused Django tests (matching existing style under `alt_text_app/tests/`).

Recommended tests:
- **Generator unit tests** (pure function tests):
  - Output is WebP.
  - Height <= 100, width <= 200.
  - Downscale behavior when `orig_h > 100`.
  - Crop behavior on wide images (left-anchored).
  - Sharpen only on downscale path.
  - EXIF orientation correctness (fixture image).
  - Decompression bomb triggers error.

- **Integration tests**:
  - Upload flow stores `thumbnail_webp`.
  - `image_preview_url` returns WebP bytes from DB.
  - If original file is missing, preview still works (because it comes from DB).

Run tests:
- `uv run ./run_tests.py`

---

## Open Questions / Decisions to Confirm
- **Is thumbnail mandatory?**
  - If yes: fail the upload if thumbnail generation fails.
  - Answer: Yes -- the thumbnail is mandatory.
  - ~~If no (recommended): allow upload/alt-text to proceed, but report page preview may be missing; store `thumbnail_error`.~~

- **DB size considerations**
  - WebP thumbnails at 200x100 are usually small, but binary storage still increases DB size.
  - If DB storage is a concern long-term, consider storing thumbnails in durable object storage instead.

---

## Resume Context (for a future work session)
Key files/locations:
- Preview template tag:
  - `alt_text_app/alt_text_app_templates/alt_text_app/report.html` (image `<img src>` uses `image_preview_url`).
- Preview URL definition:
  - `config/urls.py` → `image_preview_url`.
- Current preview view (needs change):
  - `alt_text_app/views.py::image_preview()` currently streams original file from `settings.IMAGE_UPLOAD_PATH`.
- Upload workflow (place to generate thumbnail):
  - `alt_text_app/views.py::upload_image()`
  - `alt_text_app/lib/image_helpers.py::save_image_file()`.
- Thumbnail spec:
  - `alt_text_project/image_thumbnail_specification.md`.
- Dependency management:
  - `alt_text_project/pyproject.toml` and `alt_text_project/uv.lock`.

---

## Completion Definition
This change is complete when:
- The report page’s image preview is served from **DB thumbnail bytes**.
- The preview continues to work even if originals are deleted from disk.
- Thumbnail generation is spec-compliant and covered by tests.
