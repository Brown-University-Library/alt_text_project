# PLAN — Convert PDF checker into Image Alt-Text webapp

## Goal
Replace the current “PDF accessibility checker” workflow with an “image alt-text generator” workflow:

- Upload an image via a web form.
- Validate that the uploaded item is an image (not just by extension).
- Send the image **and** a prompt requesting accessibility alt-text to OpenRouter.
- Persist results and display them back to the user.

**Constraint:** implementation should follow `alt_text_project/AGENTS.md` conventions:
- Thin Django views (endpoint orchestration only).
- Put real logic in `pdf_checker_app/lib/` (or a renamed app’s `lib/`).
- Use `httpx` for HTTP.
- Use Python 3.12 typing style (builtin generics, PEP604 unions).
- Respect `ruff.toml` formatting (single quotes, line length 125).

## Current state (context for future work session)
### URLs / endpoints today
Defined in `alt_text_project/config/urls.py`:
- `pdf_uploader/` → `pdf_checker_app.views.upload_pdf`
- `pdf/report/<uuid:pk>/` → `pdf_checker_app.views.view_report`
- HTMX fragments for polling:
  - `pdf/report/<uuid:pk>/status.fragment`
  - `pdf/report/<uuid:pk>/verapdf.fragment`
  - `pdf/report/<uuid:pk>/summary.fragment`

### Upload + processing today
- Form: `pdf_checker_app/forms.py::PDFUploadForm`
  - Validates 50MB max
  - Validates `.pdf` extension
  - Validates PDF header `%PDF-`
  - Optionally uses `python-magic`
- View: `pdf_checker_app/views.py::upload_pdf`
  - Computes checksum (SHA-256)
  - Creates/updates `PDFDocument`
  - Saves file to disk under `PDF_UPLOAD_PATH` via `pdf_helpers.save_pdf_file()`
  - Attempts synchronous processing via `sync_processing_helpers.attempt_synchronous_processing()`
  - Redirects to report page
- Synchronous processing: `pdf_checker_app/lib/sync_processing_helpers.py`
  - veraPDF sync attempt (with timeout)
  - then OpenRouter sync attempt (with timeout)
  - timeouts fall back to cron scripts
- OpenRouter integration: `pdf_checker_app/lib/openrouter_helpers.py`
  - `call_openrouter()` hits `https://openrouter.ai/api/v1/chat/completions`
  - Sends `payload = {'model': model, 'messages': [{'role': 'user', 'content': prompt}]}`
  - Stores results in `OpenRouterSummary`
- DB models: `pdf_checker_app/models.py`
  - `PDFDocument` (checksum + user info + status)
  - `VeraPDFResult`
  - `OpenRouterSummary`
- Cron scripts (optional background processing):
  - `scripts/process_verapdf_jobs.py`
  - `scripts/process_openrouter_summaries.py`

### Settings / env today
In `config/settings.py`:
- veraPDF settings: `VERAPDF_PATH`, `VERAPDF_PROFILE`
- upload path: `PDF_UPLOAD_PATH`
- timeouts: `*_SYNC_TIMEOUT_SECONDS`, `*_CRON_TIMEOUT_SECONDS`
- stuck recovery: `RECOVER_STUCK_PROCESSING_AFTER_SECONDS`

Dependencies (from `pyproject.toml`):
- Django 5.2
- httpx
- python-dotenv
- python-magic
- trio

## Proposed new product behavior
### User flow (web)
1. User visits `image_uploader/`.
2. User uploads an image.
3. Server validates:
   - File size (keep 50MB unless reduced)
   - MIME type (using magic / sniff)
   - Basic “decodable image” check (optional but recommended)
4. Server computes checksum and stores the image on disk.
5. Server calls OpenRouter with:
   - A text prompt asking for **concise accessibility alt-text**.
   - The image content.
6. Server stores the generated alt text (plus raw response, model, tokens, etc.).
7. User is redirected to `image/report/<uuid>/` which displays:
   - Image metadata
   - Generated alt text
   - (Optional) raw OpenRouter response under a `<details>` section

### Background vs synchronous
For v1, prefer **synchronous-only** processing:
- Image → OpenRouter is typically much faster than veraPDF + LLM.
- Removes need for polling/fragments/cron complexity.

Optionally keep the “pending/processing/failed” status model shape so timeouts and retries can be added later with minimal churn.

## Key architectural decisions (recommended)
### 1) Decide whether to rename the Django app
Two valid approaches:

- **Minimal churn:** keep app name `pdf_checker_app` but repurpose it to image alt text.
  - Pros: fewer settings/template path changes.
  - Cons: confusing names (`PDFDocument`, `pdf_helpers`, etc.).

- **Clean rename (recommended for maintainability):** rename `pdf_checker_app` → `alt_text_app` (or similar).
  - Pros: matches new domain.
  - Cons: requires Django app rename + migrations + template path updates.

Plan below assumes **minimal churn first**, with a later optional rename step once functionality is stable.

### 2) Store images on disk, store metadata + outputs in DB
Mirror existing pattern:
- Save file to a configured directory (rename `PDF_UPLOAD_PATH` → `IMAGE_UPLOAD_PATH`).
- Use checksum as filename base.
- Store:
  - original filename
  - checksum
  - size
  - detected mime
  - uploaded_at
  - processing_status / error
  - alt text
  - raw OpenRouter response + model + usage

### 3) Image validation strategy
Recommended layered validation:
- **Size:** keep current 50MB max via Django settings + form validation.
- **Extension:** optional (nice UX), but do not rely on it.
- **Magic/MIME sniff:** use `python-magic` if available (already used).
  - Accept `image/jpeg`, `image/png`, `image/webp`, `image/gif` (optional), `image/tiff` (optional).
- **Decode check (recommended):** attempt to decode using Pillow.
  - This would require adding `Pillow` dependency.
  - If avoiding new deps is preferred, skip decode and rely on magic + basic header checks.

### 4) OpenRouter “vision” request format
Current `call_openrouter()` sends plain text.
For images, many OpenAI-compatible APIs use a **content array** with typed parts.

Implementation plan should:
- Update `openrouter_helpers.call_openrouter()` (or add a sibling function) to support:
  - `messages = [{'role': 'user', 'content': [ {'type':'text','text': prompt}, {'type':'image_url','image_url': {'url': 'data:image/...;base64,...'}} ]}]`
  - OR OpenRouter’s preferred format if it differs.
- Keep the existing `SYSTEM_CA_BUNDLE` optional handling.
- Ensure the chosen `OPENROUTER_MODEL` supports vision/image inputs.

**Important:** Confirm OpenRouter model capability + payload shape in a future session (OpenRouter docs / model card). If the model does not support images, you’ll get a 4xx error.

## Implementation plan (step-by-step)

### Milestone A — Re-scope URLs, templates, and user-facing copy
- Update `config/urls.py`:
  - Replace `pdf_uploader/` with `image_uploader/` endpoint.
  - Replace `pdf/report/<uuid:pk>/` with `image/report/<uuid:pk>/`.
  - Remove HTMX fragment endpoints for veraPDF (and possibly status/summary) if going synchronous-only.
  - Keep `info/`, `version/`, `admin/` as-is.
- Add/modify templates:
  - Replace `pdf_checker_app/upload.html` with an image upload UI.
  - Replace `pdf_checker_app/report.html` with an image report page showing:
    - a thumbnail/preview (served carefully)
    - generated alt text
    - status/errors

### Milestone B — Replace PDF form with ImageUploadForm
- In `pdf_checker_app/forms.py`:
  - Create `ImageUploadForm` with `image_file = forms.FileField(...)`.
  - Validation rules:
    - enforce max size
    - check extension against allowed list (optional)
    - validate magic/MIME is `image/*` and in allowed set
    - (optional) decode check using Pillow

### Milestone C — Replace models with image-centric models
- In `pdf_checker_app/models.py`:
  - Replace `PDFDocument` with `ImageDocument` (or similar)
  - Replace `OpenRouterSummary` with `OpenRouterAltText` (or reuse name but change semantics)
  - Remove `VeraPDFResult`

Recommended new model fields:
- `ImageDocument`
  - `id: UUID`
  - `original_filename: str`
  - `file_checksum: str` (unique)
  - `file_size: int`
  - `detected_mime: str` (new)
  - user info fields (keep if still desired)
  - timestamps
  - processing_status / processing_error
- `OpenRouterAltText`
  - one-to-one with `ImageDocument`
  - `raw_response_json`, `alt_text` (rename from `summary_text`)
  - `prompt`
  - response metadata + token counts
  - status/error + requested_at/completed_at

### Milestone D — Replace pdf_helpers with image_helpers
- Create `pdf_checker_app/lib/image_helpers.py` (or repurpose `pdf_helpers.py`) with:
  - `generate_checksum(file: UploadedFile) -> str` (can be shared)
  - `save_image_file(file: UploadedFile, checksum: str, extension: str) -> Path`
    - Use detected mime to pick an extension (don’t trust user extension).
  - `get_shibboleth_user_info(request) -> dict[...]` (if still needed)

Decide on storage naming:
- Prefer `{checksum}.{ext}` where `ext` is derived from mime.
- Store the ext/mime in DB so later you can reconstruct the path.

### Milestone E — Implement OpenRouter vision call + prompt builder
- In `pdf_checker_app/lib/openrouter_helpers.py`:
  - Replace the existing PDF-specific `PROMPT` with an image-alt-text prompt.
  - Implement `build_alt_text_prompt(...) -> str`.
  - Add `call_openrouter_with_image(...)` that:
    - accepts the prompt text
    - accepts image bytes + mime
    - base64-encodes to a `data:` URL
    - sends OpenRouter chat-completions payload

Prompt requirements (suggested):
- Ask for one or two sentences max.
- Prefer neutral, descriptive language.
- Avoid “image of…” unless needed.
- If the image appears decorative/meaningless, return empty string or “Decorative image” (choose one policy).

### Milestone F — Rewrite views to orchestrate image flow
- In `pdf_checker_app/views.py`:
  - Replace `upload_pdf()` with `upload_image()`:
    - validate form
    - compute checksum
    - look up existing completed record and reuse
    - save file
    - call “sync processing” helper (or call OpenRouter directly)
    - redirect to report
  - Replace `view_report()` with `view_image_report()`.

If keeping a sync helper module:
- Create `pdf_checker_app/lib/sync_alt_text_processing_helpers.py` (or repurpose existing) to:
  - create/update the OpenRouterAltText record
  - call OpenRouter with timeout
  - persist parsed response

### Milestone G — Settings and environment variables
- In `config/settings.py`:
  - Remove veraPDF settings: `VERAPDF_*`.
  - Rename `PDF_UPLOAD_PATH` → `IMAGE_UPLOAD_PATH`.
  - Keep file upload size limits.
  - Keep `OPENROUTER_SYNC_TIMEOUT_SECONDS` (and possibly remove cron timeouts).

- In `.env`:
  - Remove `VERAPDF_PATH`, `VERAPDF_PROFILE`.
  - Add `IMAGE_UPLOAD_PATH`.
  - Keep `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.
  - Ensure the chosen model supports image inputs.

### Milestone H — Remove cron scripts and polling (if not needed)
- Delete or deprecate:
  - `scripts/process_verapdf_jobs.py`
  - `scripts/process_openrouter_summaries.py`
- Remove fragment templates and URLs if synchronous-only:
  - `pdf_checker_app/fragments/*` (status/verapdf/summary)
  - corresponding endpoints in `urls.py`

(If you prefer to keep background processing, then instead repurpose the OpenRouter cron script to process images, but that’s a bigger v2.)

### Milestone I — Tests
- Update Django tests under `pdf_checker_app/tests/`:
  - Replace PDF tests with image upload tests:
    - **Happy path:** upload valid PNG/JPEG, get alt text persisted, redirect works
    - **Failure path:** upload a non-image file with `.png` extension → form invalid
    - **Failure path:** OpenRouter credentials missing → alt text generation skipped/failed with user-facing error
  - Ensure `uv run ./run_tests.py` continues to pass.

### Milestone J — Data migrations and cleanup
- Create new migrations for the model changes.
- Decide what to do with existing PDF-related tables:
  - In dev: can drop and recreate.
  - In prod: write migrations carefully (may require data retention decisions).

## Open questions / decisions to make before coding
- Should the app keep Shibboleth-derived user fields for images?
- Should image bytes be stored on disk only, or also in DB (not recommended for large files)?
- What max image size should be allowed (50MB may be too large for vision models and may create slow uploads)?
- Which image formats are supported?
- Which OpenRouter model will be used for vision? (must support image input)
- Should the UI show a preview image? If yes, how will it be served (static/media vs custom view)?

## Recommended “smallest correct” implementation sequence
1. Implement `ImageUploadForm` and `upload_image()` view with validation + save-to-disk.
2. Implement OpenRouter vision call + parse/persist alt-text.
3. Implement report page showing alt text.
4. Remove veraPDF-specific code paths once the new flow is working.

---

## Notes for a future implementation session
- Follow `AGENTS.md` and keep views thin; put file IO + OpenRouter logic into `lib/`.
- Keep `httpx` and the existing CA bundle handling (`SYSTEM_CA_BUNDLE`).
- The repo already uses `python-magic`; leverage it for MIME sniffing.
- `ruff.toml` indicates single quotes and line-length 125; match that style.
