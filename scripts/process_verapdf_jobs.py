#!/usr/bin/env python
"""
Deprecated veraPDF cron script.

The image alt-text maker no longer runs veraPDF. This script remains
as a no-op placeholder to avoid breaking existing cron invocations.

Usage:
    uv run ./scripts/process_verapdf_jobs.py
"""

import logging

log = logging.getLogger(__name__)


def main() -> None:
    """
    Entry point for the cron script.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s [%(module)s-%(funcName)s()::%(lineno)d] %(message)s',
        datefmt='%d/%b/%Y %H:%M:%S',
    )

    log.info('veraPDF processing is deprecated for this app; no work performed.')


if __name__ == '__main__':
    main()
