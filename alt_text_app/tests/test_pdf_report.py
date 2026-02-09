import io
import logging
import uuid

from PIL import Image
from django.test import TestCase
from django.urls import reverse

from alt_text_app.models import ImageDocument

log = logging.getLogger(__name__)
TestCase.maxDiff = 1000


class ImageReportTest(TestCase):
    """
    Checks image report functionality with UUID endpoints.
    """

    def setUp(self) -> None:
        """
        Sets up test data with UUID-based ImageDocument.
        """
        self.test_uuid = uuid.uuid4()
        self.document = ImageDocument.objects.create(
            id=self.test_uuid,
            original_filename='test.png',
            file_checksum='test_checksum_123',
            file_size=1024,
            mime_type='image/png',
            file_extension='png',
            user_first_name='Test',
            user_last_name='User',
            user_email='test@example.com',
            user_groups=['test_group'],
            processing_status='completed',
        )

    def test_image_report_url_with_valid_uuid(self) -> None:
        """
        Checks that image report URL works with valid UUID.
        """
        log.debug(f'testing with UUID: {self.test_uuid}')
        url = reverse('image_report_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'test.png')

    def test_image_report_url_with_invalid_uuid(self) -> None:
        """
        Checks that image report URL returns 404 for invalid UUID.
        """
        invalid_uuid = uuid.uuid4()
        log.debug(f'testing with invalid UUID: {invalid_uuid}')
        url = reverse('image_report_url', kwargs={'pk': invalid_uuid})
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)

    def test_image_report_url_with_malformed_uuid(self) -> None:
        """
        Checks that image report URL returns 404 for malformed UUID.
        """
        url = '/image/report/not-a-uuid/'
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)

    def test_image_preview_url_with_existing_file(self) -> None:
        """
        Checks that image preview URL streams the stored thumbnail.
        """
        thumbnail_stream = io.BytesIO()
        with Image.new('RGB', (10, 10), color='blue') as image:
            image.save(thumbnail_stream, format='WEBP')
        self.document.thumbnail_webp = thumbnail_stream.getvalue()
        self.document.save(update_fields=['thumbnail_webp'])
        url = reverse('image_preview_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertEqual('image/webp', response['Content-Type'])

    def test_image_preview_url_missing_file(self) -> None:
        """
        Checks that image preview URL returns 404 when thumbnail is missing.
        """
        url = reverse('image_preview_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)
