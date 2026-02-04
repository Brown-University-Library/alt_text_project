# Plan: Convert PDF Checker -> Image Alt-Text Maker

## Goal
Convert this Django webapp from a **PDF accessibility checker** into an **image alt-text maker** with the same high-level architecture:

- **Upload**
- **Try processing live** (within request timeouts)
- If timeouts/errors occur, **redirect to a report page** that **polls** for results while background/cron processing completes
- Use an **ordered list of OpenRouter models** (fallback model order)
- Keep the existing **pattern-library header include** mechanism

## Non-goals / explicit constraints
- No attempt to preserve existing database rows. Assume a **brand-new database** created from the updated `models.py`.
- No requirement to keep veraPDF functionality.
- Maintain existing architectural conventions from `AGENTS.md`:
  - `views.py` stays thin (orchestrator only)
  - business logic goes in `alt_text_app/lib/` 
  - use `httpx` for HTTP calls
  - Python 3.12 type hints
  - follow `ruff.toml` formatting (notably single quotes)

---

## Current architecture snapshot (as of this plan)

### URLs
`alt_text_project/config/urls.py`
- `pdf_uploader/` -> `pdf_checker_app.views.upload_pdf`
- `pdf/report/<uuid:pk>/` -> `pdf_checker_app.views.view_report`
- htmx polling fragments:
  - `.../status.fragment` -> `status_fragment`
  - `.../verapdf.fragment` -> `verapdf_fragment`
  - `.../summary.fragment` -> `summary_fragment`

### Upload & live attempt
`pdf_checker_app/views.py::upload_pdf`
- Validates upload via `PDFUploadForm`
- Computes checksum
- Creates/updates `PDFDocument`
- Saves file to `PDF_UPLOAD_PATH` via `pdf_helpers.save_pdf_file()`
- Calls `sync_processing_helpers.attempt_synchronous_processing()`
- Redirects immediately to report page

### Timeout fallback (background)
- veraPDF background: `scripts/process_verapdf_jobs.py` processes `PDFDocument` in `pending`/stuck `processing`
- OpenRouter background: `scripts/process_openrouter_summaries.py` processes docs that need summaries

### Report UI
- `report.html` includes:
  - `status_fragment.html` (polls until terminal)
  - `summary_fragment.html` (polls until OpenRouter summary done)
  - `verapdf_fragment.html` (loads once upon completion)

### Pattern-library header
- `base.html` includes:
  - `includes/pattern_header/head.html`
  - `includes/pattern_header/body.html`
- Updated manually via `manage.py update_pattern_header`.

---

## Target architecture (image alt-text maker)

### User-visible flow
1. User uploads an **image** (JPG/PNG/WebP/GIF, etc.).
2. App validates it is an image.
3. App stores it to disk and creates an `ImageDocument` record (or similar).
4. App **attempts** to call OpenRouter **multimodal** model(s) synchronously with a short timeout.
5. App redirects to a report page immediately.
6. If the synchronous call timed out, background/cron job later completes processing.
7. Report page polls until alt-text exists or processing failed.

### Endpoints (recommended)
Keep a similar URL layout (rename paths and URL names):
- `image_uploader/` -> `upload_image`
- `image/report/<uuid:pk>/` -> `view_image_report`
- fragments:
  - `image/report/<uuid:pk>/status.fragment` -> `status_fragment`
  - `image/report/<uuid:pk>/alt_text.fragment` -> `alt_text_fragment` (replacing `summary_fragment`)
  - optional `image/report/<uuid:pk>/image.fragment` if you want separate lazy-loading

### Processing model
Since the PDF checker had two phases (veraPDF then OpenRouter), the new system can be simplified:
- Single phase: **OpenRouter multimodal generation**
- Still preserve:
  - `processing_status` on the uploaded item
  - a separate result model for the OpenRouter response
  - “sync attempt” helper + cron script for retry/background

---

## Data model proposal (minimal first version)

### Rename intent
Replace PDF-specific names with image-specific names (no migration needed; new DB assumed).

### Suggested models
1. **`ImageDocument`** (replaces `PDFDocument`)
   - `id: UUID` (primary key)
   - `original_filename: str`
   - `file_checksum: str` (unique, SHA-256)
   - `file_size: int`
   - `mime_type: str` (e.g. `image/jpeg`)
   - `uploaded_at: datetime`
   - `processing_started_at: datetime | None`
   - `processing_status: 'pending' | 'processing' | 'completed' | 'failed'`
   - `processing_error: str | None`
   - (keep existing Shibboleth user fields if still desired in this app)
     - `user_first_name`, `user_last_name`, `user_email`, `user_groups`

2. **`OpenRouterAltText`** (replaces `OpenRouterSummary`)
   - `id: UUID`
   - `image_document: OneToOne(ImageDocument)`
   - `raw_response_json: JSON | None`
   - `prompt: str` (the exact prompt used)
   - `alt_text: str` (the generated alt text)
   - `status: 'pending' | 'processing' | 'completed' | 'failed'`
   - `error: str | None`
   - `requested_at`, `completed_at`, `openrouter_created_at`
   - `provider`, `model`, `finish_reason`
   - `prompt_tokens`, `completion_tokens`, `total_tokens`, `cost` (keep if useful)

### Model fields to consider later (recommendations)
Keep v1 minimal; consider adding later:
- Image-derived metadata:
  - `width`, `height` (can be extracted with Pillow)
  - `color_mode` (RGB/CMYK), `has_transparency`
- UX/QA:
  - `user_supplied_context` (optional text the user provides)
  - `language_code` (alt-text language selection)
  - `safety_flags` / `content_warnings`
- Provenance:
  - `source_url` (if later supporting URL-based ingestion)
- Multiple outputs:
  - `long_description` (for complex images)
  - structured output (e.g., JSON fields for “text in image”, “chart summary”, etc.)

---

## Image validation plan

### Where validation should live
- Form-level validation in `forms.py` (mirroring the current `PDFUploadForm.clean_pdf_file()` pattern).

### What to validate
- Size limit (reuse 50MB or adjust)
- Extension and/or `content_type` from upload
- Magic bytes check (signature validation) for common formats:
  - JPEG (starts with `FF D8 FF`)
  - PNG (starts with `89 50 4E 47 0D 0A 1A 0A`)
  - GIF (`GIF87a` / `GIF89a`)
  - WebP (RIFF…WEBP)
- If the repo already uses `python-magic`, keep it optional like today.
- Consider using Pillow (`PIL.Image.open(...).verify()`) for higher confidence (recommended if dependency is acceptable).

### Storage
- Replace `PDF_UPLOAD_PATH` with `IMAGE_UPLOAD_PATH` (or similarly named).
- Save file using checksum + original extension (or a normalized extension based on detected mime).

---

## OpenRouter multimodal request plan

### Prompt template
Replace `pdf_checker_app/lib/prompt.md` with an alt-text prompt template, e.g.:
- Ask for accessibility-focused alt text
- Include constraints:
  - concise
  - no “image of …” prefix unless you prefer
  - do not guess sensitive attributes
  - mention visible text only if clearly legible
  - optionally produce: 1) short alt text 2) longer description (future)

Keep the prompt in its own file for easy maintenance.

### Payload format (high level)
Current implementation uses:
- `messages: [{'role': 'user', 'content': prompt}]`

For multimodal, plan to send content that includes both text and image, typically:
- `messages: [{
    'role': 'user',
    'content': [
      {'type': 'text', 'text': prompt_text},
      {'type': 'image_url', 'image_url': {'url': 'data:<mime>;base64,<...>'}}
    ]
  }]`

Notes:
- Some models accept `image_url` with a remote URL; others accept `data:` URLs. For v1, `data:` is simplest.
- Implement image base64 encoding in `pdf_checker_app/lib/` helper(s), not in the view.
- Keep `call_openrouter_with_model_order()` logic as-is, but ensure each model in `OPENROUTER_MODEL_ORDER` is truly multimodal.

### Timeouts
Preserve two-tier timeouts from settings:
- `OPENROUTER_SYNC_TIMEOUT_SECONDS` (web request attempt)
- `OPENROUTER_CRON_TIMEOUT_SECONDS` (background)

---

## Preserve the “sync attempt, else background” architecture

### Synchronous attempt helper
Create/replace a helper analogous to `sync_processing_helpers.attempt_synchronous_processing()` that:
- Sets `ImageDocument.processing_status = 'processing'`
- Creates/updates `OpenRouterAltText(status='processing')`
- Builds prompt
- Calls OpenRouter with timeout
- On success:
  - stores parsed `alt_text`
  - sets statuses to `completed`
- On timeout:
  - sets `OpenRouterAltText.status = 'pending'`
  - sets `ImageDocument.processing_status = 'pending'` (so cron will pick it up)
- On other errors:
  - sets statuses to `failed` and stores error

### Background/cron processing
Repurpose `scripts/process_openrouter_summaries.py` into something like `process_openrouter_alt_texts.py`:
- Find `ImageDocument` needing alt text:
  - `processing_status in ('pending', 'processing')` with stuck processing recovery logic (optional, mirroring current)
  - or based on `OpenRouterAltText.status in ('pending', 'failed')`
- Run OpenRouter with longer timeout
- Persist results

If you keep the “stuck processing recovery” behavior, reuse:
- `RECOVER_STUCK_PROCESSING_AFTER_SECONDS`

---

## Template/UI plan

### Upload page
Update `upload.html`:
- Change title/text from PDF checker to “Alt Text Maker”
- Update input `accept` attribute to image types
- Update drop-zone text to “drag and drop your image here”
- Keep the processing indicator (now “Processing image…”) and submit disable behavior

### Report page
Update `report.html` (or new template path):
- Show:
  - original filename
  - uploaded time
  - file size
  - status
- Add an **image preview** (optional but recommended):
  - Either serve from a Django endpoint that reads the stored file and returns it
  - Or store uploads in a location served by the web server (production concern)
- Replace veraPDF sections with:
  - “Generated Alt Text” section
  - “Model metadata” section (model name, timestamps)
  - Raw JSON details (optional collapse) if useful for debugging

### htmx fragments
- Keep the polling pattern:
  - `status_fragment.html` polls until terminal
  - `alt_text_fragment.html` polls until `OpenRouterAltText.status` is terminal

---

## Settings and environment variables

### Remove/retire PDF-specific settings
- `VERAPDF_PATH`, `VERAPDF_*` timeouts, `PDF_UPLOAD_PATH`, `VERAPDF_PROFILE` become irrelevant.

### Add image equivalents
- `IMAGE_UPLOAD_PATH`
- keep existing:
  - `OPENROUTER_API_KEY`
  - `OPENROUTER_MODEL_ORDER`
  - `SYSTEM_CA_BUNDLE`
  - sync/cron timeouts (may reuse existing names)

### Pattern header remains
No change needed; keep `PATTERN_HEADER_URL` and the management command mechanism.

---

## Tests (recommended minimum)

Using Django’s test framework:
- Form validation:
  - accepts valid PNG/JPG
  - rejects non-image bytes
  - rejects oversized file
- Helper logic:
  - checksum generation still works for images
  - OpenRouter response parsing extracts alt text correctly
- View flow:
  - POST upload redirects to report
  - report fragments return expected HTML given status transitions

(Where external OpenRouter calls occur, mock `httpx` calls.)

---

## Recommended implementation strategy (staged vs all-at-once)

### Recommendation: do it in **two stages**
Reason: the shift from “PDF + veraPDF + OpenRouter” to “Image + OpenRouter-only” touches many files; staging reduces the risk of breaking the routing/UI while refactoring.

#### Stage 1: deliver the new user path end-to-end (minimal, working)
- Replace upload form to accept/validate images
- Store image files
- New models (`ImageDocument`, `OpenRouterAltText`)
- Implement OpenRouter multimodal call in `lib/` with model-order fallback
- Report page + htmx polling shows alt text when ready
- Keep pattern header includes unchanged

#### Stage 2: cleanup & consolidation
- Remove/retire veraPDF scripts and helpers
- Remove verapdf fragments/templates
- Rename remaining PDF-oriented identifiers (URL names, template text, `X-Title` header value in OpenRouter request)
- Update `.env` expectations (e.g. `IMAGE_UPLOAD_PATH`)
- Update tests accordingly

If you prefer, Stage 2 can be folded into Stage 1, but it will be a larger “big bang” change.

---

## Session handoff notes (context for a future work session)

### Key files you’ll edit in the conversion
- `config/urls.py`
- `config/settings.py` (upload path settings + cleanup)
- `pdf_checker_app/models.py`
- `pdf_checker_app/forms.py`
- `pdf_checker_app/views.py`
- `pdf_checker_app/lib/openrouter_helpers.py` (multimodal payload)
- `pdf_checker_app/lib/prompt.md` (new prompt)
- Templates under `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/`
- `scripts/process_openrouter_summaries.py` (repurpose)

### Commands you’ll likely run (later, during implementation)
- `uv run ./manage.py makemigrations`
- `uv run ./manage.py migrate`
- `uv run ./manage.py runserver`
- `uv run ./run_tests.py`

### Open questions / decisions to make early
- Should the Django app package be renamed from `pdf_checker_app` to something like `alt_text_app`?
  - Renaming is doable but increases churn; you can keep the package name and just rename user-facing text + models.
  - USER-ANSWER: yes, rename the app package to `alt_text_app`.
- How will images be served for preview on the report page?
  - simplest: add a view that streams the stored file by checksum (ensure access control if needed).
  - USER-ANSWER: sure, streaming the stored file is fine for now
- Which OpenRouter models will be in `OPENROUTER_MODEL_ORDER`?
  - ensure they support image input.
  - USER-ANSWER: don't worry about this -- I'll set this in the .env -- it should not affect the code.

---

## Completion definition
The conversion is complete when:
- Upload accepts only valid images.
- Upload triggers an OpenRouter multimodal request with prompt + image.
- Result (alt text) appears on the report page.
- Sync attempt uses short timeout; timeout falls back to pending + polling + cron.
- Model-order fallback remains in effect.
- Pattern header includes remain functional.
- Updated tests pass.
