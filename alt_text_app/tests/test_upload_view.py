"""
Tests for the image upload view.
"""

import base64
import hashlib
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.urls import reverse

from alt_text_app.models import ImageDocument


class ImageUploadViewTest(TestCase):
    """
    Checks upload view behaviors.
    """

    def test_upload_creates_document_and_saves_file(self) -> None:
        """
        Checks that uploading an image creates a document and writes the file.
        """
        fixture_path = Path(__file__).resolve().parent / 'fixtures' / 'valid_image.png.b64'
        image_bytes = base64.b64decode(
            fixture_path.read_text(encoding='utf-8')
        )  # the image just contains a black dot on a white backround.
        upload = SimpleUploadedFile('valid_image.png', image_bytes, content_type='image/png')
        expected_checksum = hashlib.sha256(image_bytes).hexdigest()

        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(IMAGE_UPLOAD_PATH=temp_dir):
                with patch('alt_text_app.views.sync_processing_helpers.attempt_synchronous_processing'):
                    response = self.client.post(
                        reverse('image_upload_url'),
                        {'image_file': upload},
                    )
                self.assertEqual(302, response.status_code)
                self.assertEqual(1, ImageDocument.objects.count())
                document = ImageDocument.objects.first()
                self.assertIsNotNone(document)
                self.assertEqual('valid_image.png', document.original_filename)
                self.assertEqual(expected_checksum, document.file_checksum)
                self.assertEqual('pending', document.processing_status)

                expected_path = Path(temp_dir) / f'{expected_checksum}.png'
                self.assertTrue(expected_path.exists())
                self.assertEqual(image_bytes, expected_path.read_bytes())
