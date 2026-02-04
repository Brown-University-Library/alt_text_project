"""
Synchronous image processing helpers with timeout fallback.
Handles OpenRouter processing attempts with graceful degradation.

Called by:
    - alt_text_app.views.upload_image()
"""

import datetime
import logging
from pathlib import Path

import httpx
from django.conf import settings as project_settings
from django.utils import timezone as django_timezone

from alt_text_app.lib import image_helpers, openrouter_helpers
from alt_text_app.models import ImageDocument, OpenRouterAltText

log = logging.getLogger(__name__)


def attempt_synchronous_processing(doc: ImageDocument, image_path: Path) -> None:
    """
    Attempts to run OpenRouter synchronously with timeouts.
    Updates doc status in-place. Falls back to 'pending' on timeout.
    """
    ## Mark as processing and set timestamp
    doc.processing_status = 'processing'
    doc.processing_error = None
    doc.processing_started_at = datetime.datetime.now()
    doc.save(update_fields=['processing_status', 'processing_error', 'processing_started_at'])

    attempt_openrouter_sync(doc, image_path)


def attempt_openrouter_sync(doc: ImageDocument, image_path: Path) -> bool:
    """
    Attempts synchronous OpenRouter alt-text generation with timeout.
    Returns True if successful, False if timeout or error.
    """
    api_key = openrouter_helpers.get_api_key()
    model_order = openrouter_helpers.get_model_order()

    if not api_key or not model_order:
        log.warning('OpenRouter credentials not available, skipping sync attempt for document %s', doc.pk)
        return False

    timeout_seconds = project_settings.OPENROUTER_SYNC_TIMEOUT_SECONDS

    ## Create alt-text record with 'processing' status BEFORE calling API
    utc_now = datetime.datetime.now(tz=datetime.timezone.utc)
    naive_now = django_timezone.make_naive(utc_now)
    alt_text_record, created = OpenRouterAltText.objects.get_or_create(
        image_document=doc,
        defaults={'status': 'processing', 'requested_at': naive_now},
    )

    if not created:
        alt_text_record.status = 'processing'
        alt_text_record.requested_at = naive_now
        alt_text_record.error = None
        alt_text_record.save(update_fields=['status', 'requested_at', 'error'])

    try:
        log.info('Attempting synchronous OpenRouter for document %s', doc.pk)

        prompt = openrouter_helpers.build_prompt()

        ## Save prompt
        alt_text_record.prompt = prompt
        alt_text_record.save(update_fields=['prompt'])

        image_data_url = image_helpers.build_image_data_url(image_path, doc.mime_type)

        ## Call API with timeout
        response_json = openrouter_helpers.call_openrouter_with_model_order(
            prompt,
            api_key,
            model_order,
            timeout_seconds,
            image_data_url,
        )
        parsed = openrouter_helpers.parse_openrouter_response(response_json)

        ## Persist
        openrouter_helpers.persist_openrouter_alt_text(alt_text_record, response_json, parsed)
        doc.processing_status = 'completed'
        doc.processing_error = None
        doc.save(update_fields=['processing_status', 'processing_error'])
        log.info('Synchronous OpenRouter succeeded for document %s', doc.pk)
        return True

    except httpx.TimeoutException:
        log.warning('OpenRouter timed out for document %s, falling back to cron', doc.pk)
        alt_text_record.status = 'pending'
        alt_text_record.error = 'Sync attempt timed out; will retry in background.'
        alt_text_record.save(update_fields=['status', 'error'])
        doc.processing_status = 'pending'
        doc.processing_started_at = None
        doc.save(update_fields=['processing_status', 'processing_started_at'])
        return False

    except Exception as exc:
        log.exception('OpenRouter failed for document %s', doc.pk)
        alt_text_record.status = 'failed'
        alt_text_record.error = str(exc)
        alt_text_record.save(update_fields=['status', 'error'])
        doc.processing_status = 'failed'
        doc.processing_error = str(exc)
        doc.save(update_fields=['processing_status', 'processing_error'])
        return False
