#!/usr/bin/env python
"""
Cron-driven script to generate OpenRouter alt text for pending images.

Finds ImageDocument rows with pending/failed alt-text generation,
calls OpenRouter API, and persists the results.

Usage:
    uv run ./scripts/process_openrouter_summaries.py [--batch-size N] [--dry-run]

Requires:
    OPENROUTER_API_KEY environment variable to be set.
    OPENROUTER_MODEL_ORDER environment variable to be set.
"""

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

## Django setup - must happen before importing Django models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

## Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

log = logging.getLogger(__name__)

import django  # noqa: E402

django.setup()

from django.conf import settings as project_settings  # noqa: E402
from django.db.models import Q  # noqa: E402
from django.utils import timezone as django_timezone  # noqa: E402

from alt_text_app.lib import image_helpers, openrouter_helpers  # noqa: E402
from alt_text_app.models import ImageDocument, OpenRouterAltText  # noqa: E402


def get_api_key() -> str:
    """
    Retrieves the OpenRouter API key from environment.
    """
    return openrouter_helpers.get_api_key()


def find_pending_alt_text(batch_size: int) -> list[ImageDocument]:
    """
    Finds ImageDocument rows that need alt-text generation.
    Criteria:
    - processing_status in ('pending', 'processing')
    - does NOT have an OpenRouterAltText OR has one with status 'pending'/'failed'
    """
    docs_without_alt_text = (
        ImageDocument.objects.filter(processing_status__in=['pending', 'processing'])
        .exclude(openrouter_alt_text__isnull=False)
        .order_by('uploaded_at')[:batch_size]
    )

    docs_with_pending_alt_text = (
        ImageDocument.objects.filter(processing_status__in=['pending', 'processing'])
        .filter(Q(openrouter_alt_text__status='pending') | Q(openrouter_alt_text__status='failed'))
        .order_by('uploaded_at')[:batch_size]
    )

    doc_ids: set[str] = set()
    result: list[ImageDocument] = []
    for doc in list(docs_without_alt_text) + list(docs_with_pending_alt_text):
        if str(doc.pk) not in doc_ids and len(result) < batch_size:
            doc_ids.add(str(doc.pk))
            result.append(doc)

    return result


def get_model_order() -> list[str]:
    """
    Retrieves the OpenRouter model order from environment.
    """
    return openrouter_helpers.get_model_order()


def process_single_alt_text(doc: ImageDocument, api_key: str, model_order: list[str]) -> bool:
    """
    Generates and saves OpenRouter alt text for a single image.
    Returns True on success, False on failure.
    Called by process_alt_texts()
    """
    log.info('Processing alt text for document %s (%s)', doc.pk, doc.original_filename)

    alt_text_record: OpenRouterAltText
    created: bool
    utc_now = datetime.now(tz=timezone.utc)
    naive_now = django_timezone.make_naive(utc_now)
    alt_text_record, created = OpenRouterAltText.objects.get_or_create(
        image_document=doc,
        defaults={'status': 'processing', 'requested_at': naive_now},
    )

    if not created:
        utc_now = datetime.now(tz=timezone.utc)
        naive_now = django_timezone.make_naive(utc_now)
        alt_text_record.status = 'processing'
        alt_text_record.requested_at = naive_now
        alt_text_record.error = None
        alt_text_record.save(update_fields=['status', 'requested_at', 'error'])

    success = False
    try:
        image_path = image_helpers.get_image_path(doc.file_checksum, doc.file_extension)
        if not image_path.exists():
            raise FileNotFoundError(f'Image file not found: {image_path}')

        prompt = openrouter_helpers.build_prompt()
        log.debug('Calling OpenRouter for document %s', doc.pk)

        alt_text_record.prompt = prompt
        alt_text_record.save(update_fields=['prompt'])

        image_data_url = image_helpers.build_image_data_url(image_path, doc.mime_type)

        timeout_seconds = project_settings.OPENROUTER_CRON_TIMEOUT_SECONDS
        response_json = openrouter_helpers.call_openrouter_with_model_order(
            prompt,
            api_key,
            model_order,
            timeout_seconds,
            image_data_url,
        )

        parsed = openrouter_helpers.parse_openrouter_response(response_json)
        openrouter_helpers.persist_openrouter_alt_text(alt_text_record, response_json, parsed)

        doc.processing_status = 'completed'
        doc.processing_error = None
        doc.save(update_fields=['processing_status', 'processing_error'])

        log.info('Successfully generated alt text for document %s', doc.pk)
        success = True

    except Exception as exc:
        log.exception('Failed to generate alt text for document %s', doc.pk)
        alt_text_record.status = 'failed'
        alt_text_record.error = str(exc)
        alt_text_record.save(update_fields=['status', 'error'])
        doc.processing_status = 'failed'
        doc.processing_error = str(exc)
        doc.save(update_fields=['processing_status', 'processing_error'])

    return success


def process_alt_texts(batch_size: int, dry_run: bool) -> tuple[int, int]:
    """
    Finds and processes pending OpenRouter alt-text jobs.
    Returns (success_count, failure_count).
    """
    api_key = get_api_key()
    if not api_key:
        log.error('OPENROUTER_API_KEY environment variable not set')
        return (0, 0)

    model_order = get_model_order()
    if not model_order:
        log.error('OPENROUTER_MODEL_ORDER environment variable not set')
        return (0, 0)

    docs = find_pending_alt_text(batch_size)
    log.info('Found %s documents needing alt text', len(docs))

    if dry_run:
        for doc in docs:
            log.info('[DRY RUN] Would generate alt text for: %s (%s)', doc.pk, doc.original_filename)
        return (0, 0)

    success_count = 0
    failure_count = 0

    for doc in docs:
        if process_single_alt_text(doc, api_key, model_order):
            success_count += 1
        else:
            failure_count += 1

    return (success_count, failure_count)


def main() -> None:
    """
    Entry point for the cron script.
    """
    parser = argparse.ArgumentParser(description='Generate OpenRouter alt text for pending images')
    parser.add_argument(
        '--batch-size',
        type=int,
        default=1,
        help='Maximum number of summaries to generate in one run (default: 1)',
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without actually calling the API',
    )
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose logging',
    )
    args = parser.parse_args()

    ## Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
        datefmt='%d/%b/%Y %H:%M:%S',
    )

    log.info('Starting OpenRouter alt-text processor')
    success_count, failure_count = process_alt_texts(args.batch_size, args.dry_run)
    log.info(f'Finished: {success_count} succeeded, {failure_count} failed')


if __name__ == '__main__':
    main()
