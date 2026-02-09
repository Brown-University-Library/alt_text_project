"""
Helper functions for image processing.

Called by:
    - alt_text_app.views.upload_image() (file operations, checksum generation)
    - alt_text_app.lib.sync_processing_helpers (synchronous OpenRouter attempts)
"""

import base64
import hashlib
import logging
from pathlib import Path

from django.conf import settings as project_settings
from django.core.files.uploadedfile import UploadedFile

log = logging.getLogger(__name__)


def get_shibboleth_user_info(request) -> dict[str, str | list[str]]:
    """
    Extracts Shibboleth user information from request headers.
    """
    ## These header names may vary depending on your Shibboleth configuration
    ## Adjust as needed based on your Shibboleth SP configuration
    return {
        'first_name': request.META.get('HTTP_SHIB_GIVEN_NAME', ''),
        'last_name': request.META.get('HTTP_SHIB_SN', ''),
        'email': request.META.get('HTTP_SHIB_MAIL', ''),
        'groups': request.META.get('HTTP_SHIB_GROUPS', '').split(';') if request.META.get('HTTP_SHIB_GROUPS') else [],
    }


def generate_checksum(file: UploadedFile) -> str:
    """
    Generates SHA-256 checksum for uploaded file.
    """
    sha256_hash = hashlib.sha256()
    for chunk in file.chunks():
        sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def save_image_file(file: UploadedFile, checksum: str, extension: str) -> Path:
    """
    Saves uploaded image file to storage.
    Called by:
        - alt_text_app.views.upload_image()
    """
    upload_dir_path = Path(project_settings.IMAGE_UPLOAD_PATH)
    absolute_upload_dir_path = upload_dir_path.resolve()
    absolute_upload_dir_path.mkdir(parents=True, exist_ok=True)
    safe_extension = extension.lower().lstrip('.')
    upload_image_path = absolute_upload_dir_path / f'{checksum}.{safe_extension}'

    with open(upload_image_path, 'wb') as dest:
        for chunk in file.chunks():
            dest.write(chunk)

    return upload_image_path


def get_image_path(checksum: str, extension: str) -> Path:
    """
    Builds the path to a stored image from its checksum and extension.
    """
    upload_dir_path = Path(project_settings.IMAGE_UPLOAD_PATH).resolve()
    safe_extension = extension.lower().lstrip('.')
    return upload_dir_path / f'{checksum}.{safe_extension}'


def build_image_data_url(image_path: Path, mime_type: str) -> str:
    """
    Builds a base64 data URL for an image file.
    """
    image_bytes = image_path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode('ascii')
    safe_mime_type = mime_type or 'image/*'
    return f'data:{safe_mime_type};base64,{encoded}'
