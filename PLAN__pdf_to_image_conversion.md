# Plan: Convert PDF Accessibility Checker to Image Alt-Text Generator

## Goal

Transform this webapp from:
- **Current**: Upload PDF → validate via veraPDF → send report to OpenRouter for accessibility suggestions
- **New**: Upload image → validate it's an image → send image + prompt to OpenRouter for alt-text generation

---

## Current Architecture Summary

### Key Files

| File | Purpose |
|------|---------|
| `pdf_checker_app/forms.py` | `PDFUploadForm` with PDF validation (magic bytes, extension, size) |
| `pdf_checker_app/views.py` | Upload view, report view, htmx polling fragments |
| `pdf_checker_app/models.py` | `PDFDocument`, `VeraPDFResult`, `OpenRouterSummary` |
| `pdf_checker_app/lib/pdf_helpers.py` | Checksum, file save, veraPDF execution |
| `pdf_checker_app/lib/openrouter_helpers.py` | OpenRouter API call, prompt building, response parsing |
| `pdf_checker_app/lib/sync_processing_helpers.py` | Orchestrates veraPDF + OpenRouter with timeouts |
| `config/urls.py` | URL routing |
| `config/settings.py` | veraPDF paths, timeouts, upload paths |
| `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/upload.html` | Upload form template |
| `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/report.html` | Results display template |

### Current Dependencies (from `pyproject.toml`)

- Django ~5.2.0
- httpx ~0.28.0 (for HTTP calls)
- python-dotenv ~1.1.0
- python-magic ~0.4.0 (file type detection — **keep this**)
- trio ~0.30.0

### Environment Variables (from `config/dotenv_example_file.txt` and `settings.py`)

- `OPENROUTER_API_KEY` — **keep**
- `OPENROUTER_MODEL` — **keep**
- `VERAPDF_PATH` — **remove**
- `VERAPDF_PROFILE` — **remove**
- `PDF_UPLOAD_PATH` — **rename to `IMAGE_UPLOAD_PATH`**

---

## Implementation Steps

### Phase 1: Rename App (Optional but Recommended)

**Decision needed**: Rename `pdf_checker_app` → `alt_text_app` or similar?

If yes:
1. Rename directory `pdf_checker_app/` → `alt_text_app/`
2. Update all imports throughout codebase
3. Update `INSTALLED_APPS` in `config/settings.py`
4. Update template directory name
5. Run `uv run ./manage.py makemigrations` and `uv run ./manage.py migrate`

If no: proceed with existing name (less churn, but confusing naming).

---

### Phase 2: Models (`pdf_checker_app/models.py`)

#### Remove
- `VeraPDFResult` model (no longer needed)

#### Modify `PDFDocument` → `ImageDocument`
- Rename class to `ImageDocument`
- Keep: `id`, `original_filename`, `file_checksum`, `file_size`, `user_*` fields, `uploaded_at`, `processing_started_at`, `processing_status`, `processing_error`
- Add: `mime_type` field (CharField, to store detected image type)
- Remove: any PDF-specific fields if present

#### Modify `OpenRouterSummary`
- Rename `pdf_document` ForeignKey → `image_document`
- Keep all other fields (they're generic enough for alt-text responses)
- Consider renaming `summary_text` → `alt_text` for clarity

#### Migration
```bash
uv run ./manage.py makemigrations
uv run ./manage.py migrate
```

---

### Phase 3: Forms (`pdf_checker_app/forms.py`)

#### Replace `PDFUploadForm` with `ImageUploadForm`

**Validation logic**:
1. Check file size (keep 50MB limit or adjust)
2. Check file extension: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.tiff`
3. Use `python-magic` to validate MIME type matches an image type
4. Accepted MIME types: `image/jpeg`, `image/png`, `image/gif`, `image/webp`, `image/bmp`, `image/tiff`

**Form field changes**:
- Rename `pdf_file` → `image_file`
- Update `accept` attribute: `'image/*,.jpg,.jpeg,.png,.gif,.webp,.bmp,.tiff'`
- Update label: `'Select image file'`

---

### Phase 4: Lib Modules (`pdf_checker_app/lib/`)

#### Remove
- `pdf_helpers.py` — most of this is veraPDF-specific

#### Create `image_helpers.py`
Functions needed:
- `get_shibboleth_user_info(request) -> dict` — copy from `pdf_helpers.py`
- `generate_checksum(file: UploadedFile) -> str` — copy from `pdf_helpers.py`
- `save_image_file(file: UploadedFile, checksum: str) -> Path` — adapt from `save_pdf_file()`
- `validate_image_type(file: UploadedFile) -> str` — new function, returns MIME type or raises ValidationError

#### Modify `openrouter_helpers.py`

**Remove**:
- `filter_down_failure_checks()` and related pruning functions
- `build_prompt()` (replace with new version)

**Add/Modify**:
- New `ALT_TEXT_PROMPT` constant:
  ```python
  ALT_TEXT_PROMPT = """
  Please analyze this image and provide accessibility alt-text.
  
  Requirements:
  - Describe the image content concisely but completely
  - Focus on information that would be useful for someone who cannot see the image
  - Keep the description under 150 words unless the image is complex
  - Do not start with "Image of" or "Picture of"
  - Include relevant text visible in the image
  - Describe colors, positions, and relationships between elements when meaningful
  """
  ```

- Modify `call_openrouter()` to support image input:
  - OpenRouter vision models accept base64-encoded images
  - Payload structure changes to include image content
  - Example payload:
    ```python
    {
        'model': model,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'text', 'text': prompt},
                {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{base64_image}'}}
            ]
        }]
    }
    ```

- Add `encode_image_base64(image_path: Path) -> str` function
- Add `build_alt_text_prompt() -> str` function (simple, returns the prompt constant)

#### Modify `sync_processing_helpers.py`

**Remove**:
- `attempt_verapdf_sync()` — no longer needed
- veraPDF-related imports

**Modify `attempt_synchronous_processing()`**:
- Remove veraPDF step
- Directly call OpenRouter with the image
- Simplify flow: mark processing → call OpenRouter → mark complete/failed

**Modify `attempt_openrouter_sync()`**:
- Remove veraPDF result fetching
- Read image file directly
- Encode to base64
- Call OpenRouter with image payload

---

### Phase 5: Views (`pdf_checker_app/views.py`)

#### Modify `upload_pdf()` → `upload_image()`
- Use `ImageUploadForm` instead of `PDFUploadForm`
- Use `ImageDocument` instead of `PDFDocument`
- Use `image_helpers` instead of `pdf_helpers`
- Remove veraPDF-specific logic
- Update redirect URL names

#### Modify `view_report()`
- Update to use `ImageDocument`
- Remove `VeraPDFResult` fetching
- Update template context (no verapdf_raw_json)

#### Remove or Simplify Polling Fragments
- `status_fragment()` — keep but simplify
- `verapdf_fragment()` — **remove** (no veraPDF)
- `summary_fragment()` — keep, rename context if needed

---

### Phase 6: URLs (`config/urls.py`)

#### Update paths
```python
urlpatterns = [
    ## main
    path('image_uploader/', views.upload_image, name='image_upload_url'),
    path('image/report/<uuid:pk>/', views.view_report, name='image_report_url'),
    ## htmx fragments
    path('image/report/<uuid:pk>/status.fragment', views.status_fragment, name='status_fragment_url'),
    path('image/report/<uuid:pk>/summary.fragment', views.summary_fragment, name='summary_fragment_url'),
    ## other (keep as-is)
    path('info/', views.info, name='info_url'),
    path('', views.root, name='root_url'),
    path('admin/', admin.site.urls),
    path('error_check/', views.error_check, name='error_check_url'),
    path('version/', views.version, name='version_url'),
]
```

---

### Phase 7: Templates

#### Modify `upload.html`
- Update title: "Upload Image - Alt Text Generator"
- Update heading: "Image Alt-Text Generator"
- Update description: "Upload an image to generate accessibility alt-text."
- Update form field references: `form.image_file`
- Update accept attribute for drag-drop
- Update button text: "Generate Alt-Text"

#### Modify `report.html`
- Remove veraPDF results section
- Update to show alt-text result prominently
- Add copy-to-clipboard button for alt-text
- Update heading/title

#### Remove `fragments/verapdf_fragment.html`

#### Modify `fragments/summary_fragment.html`
- Rename to `alt_text_fragment.html` (optional)
- Update display to show alt-text clearly

#### Modify `base.html`
- Update site title/branding if desired

---

### Phase 8: Settings (`config/settings.py`)

#### Remove
- `VERAPDF_PATH`
- `VERAPDF_PROFILE`
- `VERAPDF_SYNC_TIMEOUT_SECONDS`
- `VERAPDF_CRON_TIMEOUT_SECONDS`

#### Rename
- `PDF_UPLOAD_PATH` → `IMAGE_UPLOAD_PATH`

#### Keep
- `OPENROUTER_SYNC_TIMEOUT_SECONDS`
- `OPENROUTER_CRON_TIMEOUT_SECONDS`
- `FILE_UPLOAD_MAX_MEMORY_SIZE`
- `DATA_UPLOAD_MAX_MEMORY_SIZE`

#### Add (optional)
- `OPENROUTER_VISION_MODEL` — if using a different model for vision tasks

---

### Phase 9: Scripts (`scripts/`)

#### Remove
- `process_verapdf_jobs.py` — no longer needed

#### Modify `process_openrouter_summaries.py`
- Update to work with `ImageDocument` instead of `PDFDocument`
- Update to read image files and encode to base64
- Remove veraPDF result dependencies

---

### Phase 10: Tests (`pdf_checker_app/tests/`)

#### Remove or heavily modify
- `test_sync_processing.py` — remove veraPDF tests, add image processing tests

#### Modify
- `test_pdf_helpers.py` → `test_image_helpers.py`
- `test_pdf_report.py` → `test_image_report.py`
- `test_polling_endpoints.py` — update for new endpoints

#### Add new tests
- Image upload validation (valid image, invalid file, oversized file)
- OpenRouter image payload construction
- Alt-text generation happy path
- Alt-text generation failure handling

---

### Phase 11: Environment & Dependencies

#### Update `pyproject.toml`
- Rename project: `name = "alt_text_project"` (optional)
- Update description: `"Webapp to generate accessibility alt-text for images."`
- Keep `python-magic` (still needed for image validation)
- Consider removing `trio` if no longer needed (check usage)

#### Update `.env` / `dotenv_example_file.txt`
- Remove `VERAPDF_PATH`, `VERAPDF_PROFILE`
- Rename `PDF_UPLOAD_PATH` → `IMAGE_UPLOAD_PATH`
- Ensure `OPENROUTER_API_KEY` and `OPENROUTER_MODEL` are documented
- Note: model must support vision (e.g., `anthropic/claude-3.5-sonnet`, `openai/gpt-4o`)

---

### Phase 12: Documentation

#### Update `README.md`
- New project description
- Updated setup instructions
- Remove veraPDF installation requirements
- Document supported image formats
- Document OpenRouter vision model requirements

---

## OpenRouter Vision API Notes

For implementation, the OpenRouter API call for vision models uses this structure:

```python
payload = {
    'model': 'anthropic/claude-3.5-sonnet',  # or other vision-capable model
    'messages': [{
        'role': 'user',
        'content': [
            {'type': 'text', 'text': 'Describe this image for accessibility alt-text...'},
            {
                'type': 'image_url',
                'image_url': {
                    'url': f'data:image/jpeg;base64,{base64_encoded_image}'
                }
            }
        ]
    }]
}
```

The image must be base64-encoded. Use Python's `base64` module:
```python
import base64
with open(image_path, 'rb') as f:
    base64_image = base64.b64encode(f.read()).decode('utf-8')
```

---

## Coding Standards Reminder (from AGENTS.md)

- Python 3.12 type hints everywhere
- Use `httpx` for HTTP calls
- Single-return functions preferred
- Business logic in `lib/` modules, views are thin orchestrators
- Use Django's test framework
- Run tests: `uv run ./run_tests.py`
- Run Django commands: `uv run ./manage.py <command>`
- Max line length: 125 (from `ruff.toml`)
- Quote style: single quotes

---

## Suggested Implementation Order

1. **Models** — foundation for everything else
2. **Forms** — validation logic
3. **Lib modules** — `image_helpers.py`, modify `openrouter_helpers.py`
4. **Views** — wire everything together
5. **URLs** — update routing
6. **Templates** — update UI
7. **Settings** — clean up config
8. **Tests** — verify everything works
9. **Scripts** — update background processing
10. **Documentation** — update README

---

## Files to Delete (after migration)

- `pdf_checker_app/lib/pdf_helpers.py` (after extracting reusable functions)
- `scripts/process_verapdf_jobs.py`
- `pdf_checker_app/pdf_checker_app_templates/pdf_checker_app/fragments/verapdf_fragment.html`

---

## Migration Checklist

- [ ] Create new models / modify existing
- [ ] Run `makemigrations` and `migrate`
- [ ] Create `image_helpers.py`
- [ ] Modify `openrouter_helpers.py` for vision API
- [ ] Modify `sync_processing_helpers.py`
- [ ] Create `ImageUploadForm`
- [ ] Update views
- [ ] Update URLs
- [ ] Update templates
- [ ] Update settings
- [ ] Update environment variables
- [ ] Update/create tests
- [ ] Run full test suite
- [ ] Update README
- [ ] Manual testing with real images
