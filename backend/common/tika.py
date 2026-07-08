import base64
import mimetypes
import pathlib
import warnings
import filetype

from django.core.files.uploadedfile import UploadedFile
from tika_client import TikaClient
from tika_client.data_models import TikaResponse

from django.conf import settings

HEADER_PARAMS = {
    'ocr_apply_rotation': ('X-Tika-OCRApplyRotation', 'true'),
    'ocr_enable_image_processing': ('X-Tika-OCRenableImagePreprocessing', 'true'),
    'ocr_language': ('X-Tika-OCRLanguage', 'por'),
    'ocr_page_seg_mode': ('X-Tika-OCRPageSegMode', '1'),
    'ocr_page_separator': ('X-Tika-OCRPageSeparator', '1'),
    'ocr_timeout_seconds': ('X-Tika-OCRTimeoutSeconds', '60'),
    'pdf_extract_inline_images': ('X-Tika-PDFExtractInlineImages', 'true'),
    'pdf_extract_marked_content': ('X-Tika-PDFExtractMarkedContent', 'true'),
    'pdf_extract_unique_inline_images_only': (
        'X-Tika-PDFExtractUniqueInlineImagesOnly',
        'false',
    ),
    'pdf_ocr_strategy': ('X-Tika-PDFOcrStrategy', 'auto'),
    'pdf_sort_by_position': ('X-Tika-PDFSortByPosition', 'true'),
}


def tika_from_file(file, **kwargs):
    if isinstance(file, str):
        file = pathlib.Path(file)
    headers = {k: v for k, v in kwargs.items() if k in HEADER_PARAMS}
    for key in headers:
        if isinstance(headers[key], bool):
            headers[key] = str(headers[key]).lower()
    try:
        with TikaClient(tika_url=settings.TIKA_URL, timeout=90) as tika_client:
            tika_client.tika.client.headers.update(headers)
            if isinstance(file, pathlib.Path):
                response = tika_client.tika.as_text.from_buffer(
                    file.read_bytes(), mimetypes.guess_file_type(file)[0],
                )
            elif isinstance(file, UploadedFile):
                response = tika_client.tika.as_text.from_buffer(
                    file.read(), file.content_type,
                )
            if isinstance(response, TikaResponse):
                return response.data
            else:
                error = f'Unsupported source: {type(file)}'
    except Exception as e:
        error = f'Input caused an error: {str(e)}'
    warnings.warn(error)
    return {'error': error}


def tika_from_bytes(buffer: bytes, **kwargs):
    if not (mimetype := kwargs.pop('mimetype', None)):
        mimetype = filetype.guess_mime(buffer)
    headers = {
        header: kwargs.get(key, default)
        for key, (header, default) in HEADER_PARAMS.items()
    }
    for key in headers:
        if isinstance(headers[key], bool):
            headers[key] = str(headers[key]).lower()
    try:
        with TikaClient(tika_url=settings.TIKA_URL, timeout=90) as tika_client:
            tika_client.tika.client.headers.update(headers)
            response = tika_client.tika.as_text.from_buffer(buffer, mimetype)
            if isinstance(response, TikaResponse):
                return response.data
            else:
                error = response.content.decode()
    except Exception as e:
        error = f'Input caused an error: {str(e)}'
    warnings.warn(error)
    return {'error': error}


def text_from_file(file, **kwargs):
    return tika_from_file(file, **kwargs).get('X-TIKA:content', '')


def text_from_bytes(buffer: bytes, **kwargs):
    return tika_from_bytes(buffer, **kwargs).get('X-TIKA:content', '')


def tika_from_base64(content: str | bytes, **kwargs):
    return tika_from_bytes(base64.b64decode(content), **kwargs)


def text_from_base64(content: str | bytes, **kwargs):
    return tika_from_base64(content, **kwargs).get('X-TIKA:content', '')
