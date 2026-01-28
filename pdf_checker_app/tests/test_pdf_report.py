import logging
import uuid

from django.test import TestCase
from django.urls import reverse

from pdf_checker_app.models import PDFDocument

log = logging.getLogger(__name__)
TestCase.maxDiff = 1000


class PDFReportTest(TestCase):
    """
    Checks PDF report functionality with UUID endpoints.
    """

    def setUp(self):
        """
        Set up test data with UUID-based PDFDocument.
        """
        self.test_uuid = uuid.uuid4()
        self.document = PDFDocument.objects.create(
            id=self.test_uuid,
            original_filename='test.pdf',
            file_checksum='test_checksum_123',
            file_size=1024,
            user_first_name='Test',
            user_last_name='User',
            user_email='test@example.com',
            user_groups=['test_group'],
            processing_status='completed',
        )

    def test_pdf_report_url_with_valid_uuid(self):
        """
        Checks that PDF report URL works with valid UUID.
        """
        log.debug(f'testing with UUID: {self.test_uuid}')
        url = reverse('pdf_report_url', kwargs={'pk': self.test_uuid})
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        self.assertContains(response, 'test.pdf')

    def test_pdf_report_url_with_invalid_uuid(self):
        """
        Checks that PDF report URL returns 404 for invalid UUID.
        """
        invalid_uuid = uuid.uuid4()
        log.debug(f'testing with invalid UUID: {invalid_uuid}')
        url = reverse('pdf_report_url', kwargs={'pk': invalid_uuid})
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)

    def test_pdf_report_url_with_malformed_uuid(self):
        """
        Checks that PDF report URL returns 404 for malformed UUID.
        """
        url = '/pdf/report/not-a-uuid/'
        response = self.client.get(url)
        self.assertEqual(404, response.status_code)
