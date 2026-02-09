from django.contrib import admin

from alt_text_app.models import ImageDocument, OpenRouterAltText


@admin.register(ImageDocument)
class ImageDocumentAdmin(admin.ModelAdmin):
    """
    Admin interface for ImageDocument model.
    """

    list_display = [
        'original_filename',
        'user_email',
        'file_size',
        'processing_status',
        'uploaded_at',
    ]
    list_filter = [
        'processing_status',
        'uploaded_at',
    ]
    search_fields = [
        'original_filename',
        'user_email',
        'user_first_name',
        'user_last_name',
        'file_checksum',
    ]
    readonly_fields = [
        'file_checksum',
        'file_size',
        'uploaded_at',
    ]
    fieldsets = [
        ('File Information', {'fields': ['original_filename', 'file_checksum', 'file_size']}),
        ('User Information', {'fields': ['user_first_name', 'user_last_name', 'user_email', 'user_groups']}),
        ('Status', {'fields': ['processing_status', 'processing_error', 'uploaded_at']}),
    ]


@admin.register(OpenRouterAltText)
class OpenRouterAltTextAdmin(admin.ModelAdmin):
    """
    Admin interface for OpenRouterAltText model.
    """

    list_display = [
        'image_document',
        'status',
        'model',
        'provider',
        'total_tokens',
        'cost',
        'completed_at',
    ]
    list_filter = [
        'status',
        'provider',
        'model',
        'finish_reason',
        'completed_at',
    ]
    search_fields = [
        'image_document__original_filename',
        'openrouter_response_id',
        'provider',
        'model',
        'alt_text',
    ]
    readonly_fields = [
        'image_document',
        'openrouter_response_id',
        'raw_response_json',
        'requested_at',
        'completed_at',
        'openrouter_created_at',
        'prompt_tokens',
        'completion_tokens',
        'total_tokens',
        'cost',
    ]
    fieldsets = [
        ('Document', {'fields': ['image_document']}),
        ('Alt Text', {'fields': ['alt_text', 'prompt', 'status', 'error']}),
        (
            'OpenRouter Metadata',
            {
                'fields': [
                    'openrouter_response_id',
                    'provider',
                    'model',
                    'finish_reason',
                ]
            },
        ),
        (
            'Usage & Cost',
            {
                'fields': [
                    'prompt_tokens',
                    'completion_tokens',
                    'total_tokens',
                    'cost',
                ]
            },
        ),
        ('Timestamps', {'fields': ['requested_at', 'completed_at', 'openrouter_created_at']}),
        (
            'Raw Data',
            {
                'fields': ['raw_response_json'],
                'classes': ['collapse'],
            },
        ),
    ]
