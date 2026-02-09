"""
Tests for synchronous image processing with timeout fallback.
"""

import logging
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
from django.test import TestCase

from alt_text_app.lib.sync_processing_helpers import attempt_openrouter_sync
from alt_text_app.models import ImageDocument, OpenRouterAltText

log = logging.getLogger(__name__)


class SyncOpenRouterProcessingTest(TestCase):
    """
    Checks synchronous OpenRouter processing with timeout handling.
    """

    def setUp(self) -> None:
        """
        Creates a test document and image file.
        """
        self.doc = ImageDocument.objects.create(
            original_filename='test.png',
            file_checksum='abc123',
            file_size=1024,
            mime_type='image/png',
            file_extension='png',
            processing_status='pending',
        )
        self.temp_dir = tempfile.TemporaryDirectory()
        self.image_path = Path(self.temp_dir.name) / 'test.png'
        self.image_path.write_bytes(b'\x89PNG\r\n\x1a\n' + b'test')

    def tearDown(self) -> None:
        """
        Cleans up temporary files.
        """
        self.temp_dir.cleanup()

    def test_openrouter_sync_success(self) -> None:
        """
        Checks that successful OpenRouter updates alt text to 'completed'.
        """
        mock_response = {
            'id': 'test-id',
            'provider': 'test-provider',
            'model': 'test-model',
            'choices': [{'message': {'content': 'A cat on a mat.'}, 'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 20, 'total_tokens': 30},
            'created': 1234567890,
        }

        with patch('alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value='test-key'):
            with patch(
                'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                with patch(
                    'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.build_prompt',
                    return_value='test prompt',
                ):
                    with patch(
                        'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.call_openrouter_with_model_order',
                        return_value=mock_response,
                    ):
                        result = attempt_openrouter_sync(self.doc, self.image_path)

        self.assertTrue(result)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'completed')
        alt_text_record = OpenRouterAltText.objects.get(image_document=self.doc)
        self.assertEqual(alt_text_record.status, 'completed')
        self.assertEqual(alt_text_record.alt_text, 'A cat on a mat.')

    def test_openrouter_sync_timeout_fallback(self) -> None:
        """
        Checks that OpenRouter timeout sets alt-text status to 'pending'.
        """
        with patch('alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value='test-key'):
            with patch(
                'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                with patch(
                    'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.build_prompt',
                    return_value='test prompt',
                ):
                    with patch(
                        'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.call_openrouter_with_model_order',
                        side_effect=httpx.TimeoutException('timeout'),
                    ):
                        result = attempt_openrouter_sync(self.doc, self.image_path)

        self.assertFalse(result)
        alt_text_record = OpenRouterAltText.objects.get(image_document=self.doc)
        self.assertEqual(alt_text_record.status, 'pending')
        self.assertIn('timed out', alt_text_record.error)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'pending')

    def test_openrouter_sync_error_marks_failed(self) -> None:
        """
        Checks that non-timeout errors mark alt text as 'failed'.
        """
        with patch('alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value='test-key'):
            with patch(
                'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                with patch(
                    'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.build_prompt',
                    return_value='test prompt',
                ):
                    with patch(
                        'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.call_openrouter_with_model_order',
                        side_effect=Exception('API error'),
                    ):
                        result = attempt_openrouter_sync(self.doc, self.image_path)

        self.assertFalse(result)
        alt_text_record = OpenRouterAltText.objects.get(image_document=self.doc)
        self.assertEqual(alt_text_record.status, 'failed')
        self.assertIn('API error', alt_text_record.error)
        self.doc.refresh_from_db()
        self.assertEqual(self.doc.processing_status, 'failed')

    def test_openrouter_skipped_without_credentials(self) -> None:
        """
        Checks that OpenRouter is skipped if credentials are missing.
        """
        with patch('alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_api_key', return_value=''):
            with patch(
                'alt_text_app.lib.sync_processing_helpers.openrouter_helpers.get_model_order',
                return_value=['test-model'],
            ):
                result = attempt_openrouter_sync(self.doc, self.image_path)

        self.assertFalse(result)
        self.assertFalse(OpenRouterAltText.objects.filter(image_document=self.doc).exists())
