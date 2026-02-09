import logging
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase as TestCase
from django.test.utils import override_settings

from alt_text_app.lib import image_helpers

log = logging.getLogger(__name__)
TestCase.maxDiff = 1000


class ImageHelperSaveFileTest(TestCase):
    """
    Checks save_image_file storage.
    """

    def test_save_image_file_uses_image_upload_path(self) -> None:
        """
        Checks that save_image_file writes into IMAGE_UPLOAD_PATH.
        """
        content: bytes = b'\x89PNG\r\n\x1a\nimage'
        upload = SimpleUploadedFile('test.png', content, content_type='image/png')
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(IMAGE_UPLOAD_PATH=temp_dir):
                saved_path = image_helpers.save_image_file(upload, 'test_checksum_123', 'png')
                log.debug(f'saved_path, ``{saved_path}``')
                self.assertEqual(Path(temp_dir).resolve(), saved_path.parent)
                self.assertTrue(saved_path.exists())
                self.assertEqual(content, saved_path.read_bytes())


class ImageHelperPathTest(TestCase):
    """
    Checks image path helpers.
    """

    def test_get_image_path_uses_checksum_and_extension(self) -> None:
        """
        Checks that get_image_path builds the expected filename.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            with override_settings(IMAGE_UPLOAD_PATH=temp_dir):
                image_path = image_helpers.get_image_path('abc123', 'JPG')
                self.assertEqual(Path(temp_dir).resolve() / 'abc123.jpg', image_path)
