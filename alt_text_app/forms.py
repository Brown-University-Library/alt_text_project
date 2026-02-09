from django import forms
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

try:
    import magic

    MAGIC_AVAILABLE = True
except (ImportError, OSError):
    MAGIC_AVAILABLE = False


class ImageUploadForm(forms.Form):
    """
    Form for uploading image files.
    """

    image_file = forms.FileField(
        label='Select image file',
        help_text='Maximum file size: 50MB',
        widget=forms.FileInput(
            attrs={
                'accept': 'image/*',
                'class': 'form-control',
            }
        ),
    )

    def clean_image_file(self) -> UploadedFile:
        """
        Validates that the uploaded file is an image.
        """
        file = self.cleaned_data['image_file']

        ## Check file size (50MB limit)
        if file.size > 50 * 1024 * 1024:
            raise ValidationError('File size exceeds 50MB limit.')

        ## Check file extension
        allowed_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.tiff')
        if not file.name.lower().endswith(allowed_extensions):
            raise ValidationError('File must be a supported image type.')

        ## Check common image magic bytes
        file.seek(0)
        header = file.read(12)
        file.seek(0)  # Reset file pointer

        is_png = header.startswith(b'\x89PNG\r\n\x1a\n')
        is_jpeg = header.startswith(b'\xff\xd8\xff')
        is_gif = header.startswith(b'GIF87a') or header.startswith(b'GIF89a')
        is_webp = header[0:4] == b'RIFF' and header[8:12] == b'WEBP'
        is_bmp = header.startswith(b'BM')
        is_tiff = header.startswith(b'II*\x00') or header.startswith(b'MM\x00*')

        if not (is_png or is_jpeg or is_gif or is_webp or is_bmp or is_tiff):
            raise ValidationError('File must be a valid image.')

        ## If python-magic is available, use it for additional validation
        if MAGIC_AVAILABLE:
            try:
                file_type = magic.from_buffer(file.read(2048), mime=True)
                file.seek(0)  # Reset file pointer

                if not file_type.startswith('image/'):
                    raise ValidationError('File must be a valid image.')
            except Exception:
                ## If magic fails, rely on the header check above
                pass

        return file
