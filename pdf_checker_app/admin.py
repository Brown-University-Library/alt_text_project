from django.contrib import admin

from pdf_checker_app.models import OpenRouterSummary, PDFDocument, VeraPDFResult


@admin.register(PDFDocument)
class PDFDocumentAdmin(admin.ModelAdmin):
    """
    Admin interface for PDFDocument model.
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


@admin.register(VeraPDFResult)
class VeraPDFResultAdmin(admin.ModelAdmin):
    """
    Admin interface for VeraPDFResult model.
    """

    list_display = [
        'pdf_document',
        'is_accessible',
        'validation_profile',
        'passed_checks',
        'failed_checks',
        'analyzed_at',
    ]
    list_filter = [
        'is_accessible',
        'validation_profile',
        'analyzed_at',
    ]
    search_fields = [
        'pdf_document__original_filename',
        'validation_profile',
    ]
    readonly_fields = [
        'pdf_document',
        'raw_json',
        'analyzed_at',
        'verapdf_version',
    ]
    fieldsets = [
        ('Document', {'fields': ['pdf_document']}),
        (
            'Analysis Results',
            {
                'fields': [
                    'is_accessible',
                    'validation_profile',
                    'total_checks',
                    'passed_checks',
                    'failed_checks',
                ]
            },
        ),
        ('Metadata', {'fields': ['analyzed_at', 'verapdf_version']}),
        (
            'Raw Data',
            {
                'fields': ['raw_json'],
                'classes': ['collapse'],
            },
        ),
    ]


@admin.register(OpenRouterSummary)
class OpenRouterSummaryAdmin(admin.ModelAdmin):
    """
    Admin interface for OpenRouterSummary model.
    """

    list_display = [
        'pdf_document',
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
        'pdf_document__original_filename',
        'openrouter_response_id',
        'provider',
        'model',
        'summary_text',
    ]
    readonly_fields = [
        'pdf_document',
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
        ('Document', {'fields': ['pdf_document']}),
        ('Summary', {'fields': ['summary_text', 'prompt', 'status', 'error']}),
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
