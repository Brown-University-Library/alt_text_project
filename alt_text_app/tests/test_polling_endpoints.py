"""
Tests for htmx polling fragment endpoints.
"""

import logging
import uuid

from django.test import TestCase
from django.urls import reverse

from alt_text_app.models import ImageDocument, OpenRouterAltText

log = logging.getLogger(__name__)
TestCase.maxDiff = 1000


class StatusFragmentTest(TestCase):
    """
    Checks status fragment endpoint behavior.
    """

    def setUp(self) -> None:
        """
        Sets up test data.
        """
        self.test_uuid = uuid.uuid4()
        self.document = ImageDocument.objects.create(
            id=self.test_uuid,
            original_filename='test.png',
            file_checksum='test_checksum_status',
            file_size=1024,
            mime_type='image/png',
            file_extension='png',
            processing_status='pending',
        )

    def test_status_fragment_pending(self) -> None:
        """
        Checks that status fragment returns polling attributes for pending status.
        """
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'hx-trigger')
        self.assertContains(response, 'queued for processing')

    def test_status_fragment_processing(self) -> None:
        """
        Checks that status fragment returns polling attributes for processing status.
        """
        self.document.processing_status = 'processing'
        self.document.save()
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'currently being processed')

    def test_status_fragment_completed(self) -> None:
        """
        Checks that status fragment stops polling for completed status.
        """
        self.document.processing_status = 'completed'
        self.document.save()
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Processing complete')
        self.assertNotContains(response, 'hx-trigger="every')

    def test_status_fragment_failed(self) -> None:
        """
        Checks that status fragment stops polling for failed status.
        """
        self.document.processing_status = 'failed'
        self.document.save()
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Processing failed')
        self.assertNotContains(response, 'hx-trigger="every')

    def test_status_fragment_invalid_uuid(self) -> None:
        """
        Checks that status fragment returns 404 for invalid UUID.
        """
        invalid_uuid = uuid.uuid4()
        url = reverse('status_fragment_url', kwargs={'pk': invalid_uuid})
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)

    def test_status_fragment_cache_control(self) -> None:
        """
        Checks that status fragment sets Cache-Control header.
        """
        url = reverse('status_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual('no-store', response['Cache-Control'])


class AltTextFragmentTest(TestCase):
    """
    Checks alt-text fragment endpoint behavior.
    """

    def setUp(self) -> None:
        """
        Sets up test data.
        """
        self.test_uuid = uuid.uuid4()
        self.document = ImageDocument.objects.create(
            id=self.test_uuid,
            original_filename='test.png',
            file_checksum='test_checksum_alt_text',
            file_size=1024,
            mime_type='image/png',
            file_extension='png',
            processing_status='completed',
        )

    def test_alt_text_fragment_no_alt_text(self) -> None:
        """
        Checks that alt-text fragment handles missing alt text gracefully.
        """
        url = reverse('alt_text_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Alt text coming soon')

    def test_alt_text_fragment_pending(self) -> None:
        """
        Checks that alt-text fragment shows pending state with polling.
        """
        OpenRouterAltText.objects.create(
            image_document=self.document,
            status='pending',
        )
        url = reverse('alt_text_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'queued')

    def test_alt_text_fragment_processing(self) -> None:
        """
        Checks that alt-text fragment shows processing state with polling.
        """
        OpenRouterAltText.objects.create(
            image_document=self.document,
            status='processing',
        )
        url = reverse('alt_text_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'hx-get')
        self.assertContains(response, 'Generating alt text')

    def test_alt_text_fragment_completed(self) -> None:
        """
        Checks that alt-text fragment shows completed alt text.
        """
        OpenRouterAltText.objects.create(
            image_document=self.document,
            status='completed',
            alt_text='This is a test alt text.',
            model='gpt-4',
        )
        url = reverse('alt_text_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'This is a test alt text')
        self.assertContains(response, 'gpt-4')
        self.assertNotContains(response, 'hx-trigger="every')

    def test_alt_text_fragment_failed(self) -> None:
        """
        Checks that alt-text fragment shows failed state.
        """
        OpenRouterAltText.objects.create(
            image_document=self.document,
            status='failed',
            error='API error',
        )
        url = reverse('alt_text_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'Alt-text generation failed')

    def test_alt_text_fragment_cache_control(self) -> None:
        """
        Checks that alt-text fragment sets Cache-Control header.
        """
        url = reverse('alt_text_fragment_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual('no-store', response['Cache-Control'])
