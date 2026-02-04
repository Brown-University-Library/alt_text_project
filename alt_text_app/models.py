import uuid

from django.db import models


class ImageDocument(models.Model):
    """
    Stores uploaded image metadata and Shibboleth user info.
    """

    ## Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ## File identification
    original_filename = models.CharField(max_length=255)
    file_checksum = models.CharField(max_length=64, unique=True, db_index=True)  # SHA-256
    file_size = models.BigIntegerField()  # bytes
    mime_type = models.CharField(max_length=100)
    file_extension = models.CharField(max_length=10)

    ## Shibboleth user information
    user_first_name = models.CharField(max_length=100, blank=True)
    user_last_name = models.CharField(max_length=100, blank=True)
    user_email = models.EmailField(blank=True)
    user_groups = models.JSONField(default=list, blank=True)  # List of groups

    ## Timestamps
    uploaded_at = models.DateTimeField(auto_now_add=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)

    ## Status tracking
    processing_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
    )
    processing_error = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['file_checksum']),
            models.Index(fields=['-uploaded_at']),
        ]


class OpenRouterAltText(models.Model):
    """
    Stores OpenRouter alt-text results for an image.
    """

    ## Primary key
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ## Relationship
    image_document = models.OneToOneField(
        ImageDocument,
        on_delete=models.CASCADE,
        related_name='openrouter_alt_text',
    )

    ## Persistence fields
    raw_response_json = models.JSONField(null=True, blank=True)
    alt_text = models.TextField(blank=True)
    prompt = models.TextField(blank=True)

    ## Identity/metadata fields (from OpenRouter response)
    openrouter_response_id = models.CharField(max_length=128, blank=True)
    provider = models.CharField(max_length=64, blank=True)
    model = models.CharField(max_length=128, blank=True)
    finish_reason = models.CharField(max_length=32, blank=True)

    ## Status/error fields
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
    )
    error = models.TextField(blank=True, null=True)

    ## Datetime fields
    requested_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    openrouter_created_at = models.DateTimeField(null=True, blank=True)

    ## Usage/cost fields
    prompt_tokens = models.IntegerField(null=True, blank=True)
    completion_tokens = models.IntegerField(null=True, blank=True)
    total_tokens = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=6, null=True, blank=True)

    class Meta:
        verbose_name = 'OpenRouter Alt Text'
        verbose_name_plural = 'OpenRouter Alt Text'
