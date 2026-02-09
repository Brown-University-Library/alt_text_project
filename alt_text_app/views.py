import datetime
import json
import logging
import uuid
from pathlib import Path

import trio
from django.conf import settings as project_settings
from django.contrib import messages
from django.http import FileResponse, HttpRequest, HttpResponse, HttpResponseNotFound, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from alt_text_app.forms import ImageUploadForm
from alt_text_app.lib import image_helpers, markdown_helpers, sync_processing_helpers, version_helper
from alt_text_app.lib.version_helper import GatherCommitAndBranchData
from alt_text_app.models import ImageDocument, OpenRouterAltText

log = logging.getLogger(__name__)


# -------------------------------------------------------------------
# main urls
# -------------------------------------------------------------------


def root(request):
    return HttpResponseRedirect(reverse('info_url'))


def info(request):
    """
    The "about" view.
    Can get here from 'info' url, and the root-url redirects here.
    """
    log.debug('starting info()')
    ## prep data ----------------------------------------------------
    info_html: str = markdown_helpers.load_markdown_from_lib('info.md')
    context = {
        'foo': 'bar',
        'info_html': info_html,
    }
    ## prep response ------------------------------------------------
    if request.GET.get('format', '') == 'json':
        log.debug('building json response')
        resp = HttpResponse(
            json.dumps(context, sort_keys=True, indent=2),
            content_type='application/json; charset=utf-8',
        )
    else:
        log.debug('building template response')
        resp = render(request, 'alt_text_app/info.html', context)
    return resp


def upload_image(request: HttpRequest) -> HttpResponse:
    """
    Handles image upload with synchronous processing attempt.

    Attempts to call OpenRouter synchronously with timeout.
    Falls back to polling + cron if timeouts are hit.
    """
    log.debug('\n\nstarting upload_image()\n\n')
    if request.method == 'POST':
        form = ImageUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = form.cleaned_data['image_file']

            ## Get Shibboleth user info
            user_info: dict[str, str | list[str]] = image_helpers.get_shibboleth_user_info(request)

            ## Generate checksum
            checksum: str = image_helpers.generate_checksum(image_file)

            ## Check if already processed
            existing_doc: ImageDocument | None = ImageDocument.objects.filter(file_checksum=checksum).first()

            if existing_doc and existing_doc.processing_status == 'completed':
                messages.info(request, 'This image has already been processed.')
                return HttpResponseRedirect(reverse('image_report_url', kwargs={'pk': existing_doc.pk}))

            ## For pending/processing docs, redirect to report (let polling handle it)
            if existing_doc and existing_doc.processing_status in ('pending', 'processing'):
                messages.info(request, 'This image is already being processed.')
                return HttpResponseRedirect(reverse('image_report_url', kwargs={'pk': existing_doc.pk}))

            ## For failed docs, allow re-upload by resetting to pending
            if existing_doc and existing_doc.processing_status == 'failed':
                doc: ImageDocument = existing_doc
                doc.processing_status = 'pending'
                doc.processing_error = None
                doc.save(update_fields=['processing_status', 'processing_error'])
            else:
                ## Create new document record with Shibboleth user info
                doc: ImageDocument = ImageDocument.objects.create(
                    original_filename=image_file.name,
                    file_checksum=checksum,
                    file_size=image_file.size,
                    mime_type=image_file.content_type or '',
                    file_extension=Path(image_file.name).suffix.lower().lstrip('.'),
                    user_first_name=user_info['first_name'],
                    user_last_name=user_info['last_name'],
                    user_email=user_info['email'],
                    user_groups=user_info['groups'],
                    processing_status='pending',
                )

            ## Save file
            try:
                image_path: Path = image_helpers.save_image_file(
                    image_file,
                    checksum,
                    doc.file_extension,
                )
                log.debug(f'saved image file to {image_path}')
            except Exception as exc:
                log.exception('Failed to save image file')
                doc.processing_status = 'failed'
                doc.processing_error = f'Failed to save file: {exc}'
                doc.save(update_fields=['processing_status', 'processing_error'])
                messages.error(request, 'Failed to save image file. Please try again.')
                return HttpResponseRedirect(reverse('image_report_url', kwargs={'pk': doc.pk}))

            ## Attempt synchronous processing
            sync_processing_helpers.attempt_synchronous_processing(doc, image_path)

            ## Redirect to report page
            if doc.processing_status == 'completed':
                messages.success(request, 'Image processed.')
            else:
                messages.success(request, 'Image uploaded successfully. Processing in progress.')
            return HttpResponseRedirect(reverse('image_report_url', kwargs={'pk': doc.pk}))
    else:
        form: ImageUploadForm = ImageUploadForm()

    return render(request, 'alt_text_app/upload.html', {'form': form})

    ## end def upload_image()


def view_report(request, pk: uuid.UUID):
    """
    Displays the alt-text report for a processed image.
    """
    log.debug(f'starting view_report() for pk={pk}')
    doc = get_object_or_404(ImageDocument, pk=pk)

    ## Get OpenRouter alt text if it exists
    suggestions: OpenRouterAltText | None = None
    try:
        suggestions = doc.openrouter_alt_text
    except OpenRouterAltText.DoesNotExist:
        pass

    context = {
        'document': doc,
        'suggestions': suggestions,
    }
    log.debug(f'context, ``{context}``')

    return render(
        request,
        'alt_text_app/report.html',
        context,
    )


# -------------------------------------------------------------------
# htmx fragment endpoints for polling
# -------------------------------------------------------------------


def status_fragment(request, pk: uuid.UUID):
    """
    Returns a small HTML fragment for the status area.
    Used by htmx polling on the report page.
    Stops polling when processing is complete or failed.
    """
    log.debug(f'starting status_fragment() for pk={pk}')
    doc = get_object_or_404(ImageDocument, pk=pk)

    ## Determine if we should continue polling
    is_terminal = doc.processing_status in ('completed', 'failed')

    context = {
        'document': doc,
        'is_terminal': is_terminal,
    }
    log.debug(f'context, ``{context}``')

    response = render(
        request,
        'alt_text_app/fragments/status_fragment.html',
        context,
    )
    response['Cache-Control'] = 'no-store'
    return response


def alt_text_fragment(request, pk: uuid.UUID):
    """
    Returns an HTML fragment for the OpenRouter alt-text section.
    Can be polled or loaded once depending on UX preference.
    """
    log.debug(f'starting alt_text_fragment() for pk={pk}')
    doc = get_object_or_404(ImageDocument, pk=pk)

    suggestions: OpenRouterAltText | None = None
    try:
        suggestions = doc.openrouter_alt_text
    except OpenRouterAltText.DoesNotExist:
        pass

    response = render(
        request,
        'alt_text_app/fragments/alt_text_fragment.html',
        {
            'document': doc,
            'suggestions': suggestions,
        },
    )
    response['Cache-Control'] = 'no-store'
    return response


def image_preview(request, pk: uuid.UUID) -> HttpResponse:
    """
    Streams the stored image for a report-page preview.
    """
    log.debug(f'starting image_preview() for pk={pk}')
    doc = get_object_or_404(ImageDocument, pk=pk)
    if not doc.file_extension:
        return HttpResponseNotFound('<div>404 / Not Found</div>')
    image_path = image_helpers.get_image_path(doc.file_checksum, doc.file_extension)
    if not image_path.exists():
        return HttpResponseNotFound('<div>404 / Not Found</div>')
    return FileResponse(open(image_path, 'rb'), content_type=doc.mime_type or 'image/*')


# -------------------------------------------------------------------
# support urls
# -------------------------------------------------------------------


def error_check(request):
    """
    Offers an easy way to check that admins receive error-emails (in development).
    To view error-emails in runserver-development:
    - run, in another terminal window: `python -m smtpd -n -c DebuggingServer localhost:1026`,
    - (or substitue your own settings for localhost:1026)
    """
    log.debug('starting error_check()')
    log.debug(f'project_settings.DEBUG, ``{project_settings.DEBUG}``')
    if project_settings.DEBUG is True:  # localdev and dev-server; never production
        log.debug('triggering exception')
        raise Exception('Raising intentional exception to check email-admins-on-error functionality.')
    else:
        log.debug('returning 404')
        return HttpResponseNotFound('<div>404 / Not Found</div>')


def version(request):
    """
    Returns basic branch and commit data.
    """
    log.debug('starting version()')
    rq_now = datetime.datetime.now()
    gatherer = GatherCommitAndBranchData()
    trio.run(gatherer.manage_git_calls)
    info_txt = f'{gatherer.branch} {gatherer.commit}'
    context = version_helper.make_context(request, rq_now, info_txt)
    output = json.dumps(context, sort_keys=True, indent=2)
    log.debug(f'output, ``{output}``')
    return HttpResponse(output, content_type='application/json; charset=utf-8')
