"""
Helper functions for OpenRouter API integration.

Called by:
    - alt_text_app.lib.sync_processing_helpers (synchronous attempts)
    - scripts.process_openrouter_summaries (cron background processing)
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx
from django.conf import settings as project_settings
from django.utils import timezone as django_timezone

from alt_text_app.models import OpenRouterAltText

log = logging.getLogger(__name__)

OPENROUTER_API_URL = 'https://openrouter.ai/api/v1/chat/completions'

PROMPT_FILE_PATH = Path(__file__).resolve().parent / 'prompt.md'


def load_prompt_template() -> str:
    """
    Loads the OpenRouter prompt template from disk.
    """
    prompt_text = PROMPT_FILE_PATH.read_text(encoding='utf-8')
    return prompt_text


def get_api_key() -> str:
    """
    Retrieves the OpenRouter API key from environment.
    """
    log.debug('starting get_api_key()')
    key = project_settings.OPENROUTER_API_KEY
    log.debug(f'key, ``{key}``')
    return key


def get_model_order() -> list[str]:
    """
    Retrieves the OpenRouter model order from environment.
    """
    return list(project_settings.OPENROUTER_MODEL_ORDER)


def build_prompt() -> str:
    """
    Builds the prompt for OpenRouter.
    """
    prompt = load_prompt_template()
    log.debug(f'prompt, ``{prompt}``')
    return prompt


def call_openrouter(prompt: str, api_key: str, model: str, timeout_seconds: float, image_data_url: str) -> dict:
    """
    Calls the OpenRouter API with the given prompt.
    Returns the raw response JSON.

    Raises:
        httpx.TimeoutException: If the request exceeds timeout_seconds.
        httpx.HTTPStatusError: If the API returns an error status.

    Note: Only one of our servers requires a non-default certificate to be specified,
          so the SYSTEM_CA_BUNDLE environment variable is implemented optionally.
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'HTTP-Referer': 'https://library.brown.edu',
        'X-Title': 'Image Alt Text Maker',
    }

    payload = {
        'model': model,
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': prompt},
                    {'type': 'image_url', 'image_url': {'url': image_data_url}},
                ],
            }
        ],
    }

    client_kwargs = {'timeout': timeout_seconds}
    system_ca_bundle = project_settings.SYSTEM_CA_BUNDLE
    if system_ca_bundle:
        client_kwargs['verify'] = system_ca_bundle

    with httpx.Client(**client_kwargs) as client:
        response = client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        log.debug(f'response, ``{response}``')
        if response.is_error:
            log.error(
                'OpenRouter request failed with status=%s, model=%s, response=%s',
                response.status_code,
                model,
                response.text,
            )
        response.raise_for_status()
        jsn_response = response.json()
        log.debug(f'jsn_response, ``{jsn_response}``')
        return jsn_response

    ## end def call_openrouter()


def call_openrouter_with_model_order(
    prompt: str,
    api_key: str,
    model_order: list[str],
    timeout_seconds: float,
    image_data_url: str,
) -> dict:
    """
    Calls OpenRouter with models in the provided order until one succeeds.
    """
    last_exception: Exception | None = None
    response_json: dict = {}
    log.debug('OpenRouter model order: %s', model_order)

    for index, model in enumerate(model_order, start=1):
        try:
            log.info('OpenRouter attempt %s/%s with model=%s', index, len(model_order), model)
            response_json = call_openrouter(prompt, api_key, model, timeout_seconds, image_data_url)
            last_exception = None
            break
        except Exception as exc:
            last_exception = exc
            log.warning('OpenRouter call failed for model=%s, trying next if available', model)

    if last_exception is not None:
        raise last_exception

    return response_json

    ## end def call_openrouter_with_model_order()


def parse_openrouter_response(response_json: dict) -> dict:
    """
    Parses the OpenRouter response and extracts relevant fields.
    """
    result = {
        'alt_text': '',
        'openrouter_response_id': response_json.get('id', ''),
        'provider': response_json.get('provider', ''),
        'model': response_json.get('model', ''),
        'finish_reason': '',
        'openrouter_created_at': None,
        'prompt_tokens': None,
        'completion_tokens': None,
        'total_tokens': None,
    }

    ## Extract alt text from choices
    choices = response_json.get('choices', [])
    if choices:
        choice = choices[0]
        message = choice.get('message', {})
        content = message.get('content', '')
        if isinstance(content, list):
            content_text_items = [
                item.get('text', '') for item in content if isinstance(item, dict) and item.get('type') == 'text'
            ]
            result['alt_text'] = '\n'.join([text for text in content_text_items if text]).strip()
        else:
            result['alt_text'] = str(content).strip()
        result['finish_reason'] = choice.get('finish_reason', '')

    ## Extract usage info
    usage = response_json.get('usage', {})
    result['prompt_tokens'] = usage.get('prompt_tokens')
    result['completion_tokens'] = usage.get('completion_tokens')
    result['total_tokens'] = usage.get('total_tokens')

    ## Extract created timestamp
    created = response_json.get('created')
    if created:
        utc_dt = datetime.fromtimestamp(created, tz=timezone.utc)
        result['openrouter_created_at'] = django_timezone.make_naive(utc_dt)

    return result

    ## end def parse_openrouter_response()


def persist_openrouter_alt_text(alt_text_record: OpenRouterAltText, response_json: dict, parsed: dict) -> None:
    """
    Persists the OpenRouter response to the alt-text model instance.
    """
    alt_text_record.raw_response_json = response_json
    alt_text_record.alt_text = parsed['alt_text']
    alt_text_record.openrouter_response_id = parsed['openrouter_response_id']
    alt_text_record.provider = parsed['provider']
    alt_text_record.model = parsed['model']
    alt_text_record.finish_reason = parsed['finish_reason']
    alt_text_record.openrouter_created_at = parsed['openrouter_created_at']
    alt_text_record.prompt_tokens = parsed['prompt_tokens']
    alt_text_record.completion_tokens = parsed['completion_tokens']
    alt_text_record.total_tokens = parsed['total_tokens']
    utc_now = datetime.now(tz=timezone.utc)
    naive_now = django_timezone.make_naive(utc_now)
    alt_text_record.status = 'completed'
    alt_text_record.completed_at = naive_now
    alt_text_record.error = None
    alt_text_record.save()
