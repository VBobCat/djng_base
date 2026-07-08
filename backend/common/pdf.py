import base64
import mimetypes
import tempfile
import warnings
from html import escape as html_escape
from os.path import splitext
from pathlib import Path
from zipfile import ZipFile

import filetype
import pathvalidate
from django.utils.text import slugify
from PIL import Image, ImageSequence

from common.email import email_to_graphdata, html_message
from common.gotenberg import html_to_pdf, office_to_pdf
from common.misc import ensure_dir

OFFICE_MIMETYPES = [
    'application/msword',
    'application/postscript',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.ms-powerpoint.template.macroEnabled.12',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.template',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.template',
    'application/x-shockwave-flash',
    'application/xhtml+xml',
    'text/plain',
    'text/xml'
]


def converter_arquivo(att_path: Path | str, content_type: str = None) -> list[Path]:
    att_path = Path(att_path)
    mimetype = content_type
    if not mimetype:
        try:
            mimetype = filetype.guess_mime(att_path)
        except PermissionError as permission_error:
            print(permission_error)
    if not mimetype:
        mimetype = mimetypes.guess_type(att_path.name)[0] or 'application/octet-stream'
    try:
        if mimetype == 'application/pdf':
            return [att_path]
        elif mimetype == 'image/tiff':
            return converter_tiff(att_path)
        elif mimetype == 'image/svg+xml':
            return converter_svg(att_path)
        elif mimetype.startswith('image'):
            return converter_image(att_path)
        elif mimetype == 'text/html':
            return converter_html(att_path)
        elif mimetype in OFFICE_MIMETYPES:
            return converter_office(att_path)
        elif mimetype == 'application/zip':
            return converter_zip(att_path)
        elif mimetype == 'message/rfc822' or 'application/pkcs7-mime':
            return converter_eml(att_path)
    except Exception as exception:
        warnings.warn(f'Error converting {att_path}: {exception}')
        pass
    return converter_unconvertible(att_path, mimetype)


def converter_tiff(tiff_path: Path):
    path_pdf = Path(splitext(tiff_path)[0] + '.pdf')
    source_image = Image.open(tiff_path)
    page_images = [page.convert("RGB") for page in ImageSequence.Iterator(source_image)]
    page_images[0].save(path_pdf, save_all=True, append_images=page_images[1:])
    return [path_pdf]


def converter_svg(svg_path: Path):
    import cairosvg
    path_pdf = Path(splitext(svg_path)[0] + '.pdf')
    with svg_path.open(mode='rb') as svg_file, path_pdf.open(mode='wb') as pdf_file:
        cairosvg.svg2png(file_obj=svg_file, write_to=pdf_file)
    return [path_pdf]


def converter_image(image_path: Path):
    path_pdf = Path(splitext(image_path)[0] + '.pdf')
    image = Image.open(image_path)
    try:
        rgb_image = image.convert('RGB')
    except OSError:
        rgb_image = image.copy()
    rgb_image.save(path_pdf)
    return [path_pdf]


def converter_html(document_path: Path):
    path_pdf = Path(splitext(document_path)[0] + '.pdf')
    path_pdf.write_bytes(html_to_pdf(document_path).content)
    return [path_pdf]


def converter_office(document_path: Path):
    path_pdf = Path(splitext(document_path)[0] + '.pdf')
    path_pdf.write_bytes(office_to_pdf(document_path).content)
    return [path_pdf]


def converter_zip(zip_path: Path):
    conversion_path = zip_path.parent / '__zip__'
    conversion_list: list[Path] = []
    with ZipFile(zip_path, 'r') as zip_sourcefile:
        zip_sourcefile.extractall(conversion_path)
    for path in conversion_path.rglob('*'):
        if not path.is_file(): continue
        conversion_list.extend(converter_arquivo(path))
    return conversion_list


def converter_eml(eml_path: Path):
    graphdata = email_to_graphdata(eml_path)
    return converter_graphdata(graphdata, eml_path.parent)


def converter_graphdata(graphdata: dict, dump_path: Path = None):
    source_paths: list[Path] = []
    if dump_path is None:
        dump_path = Path(tempfile.gettempdir()) / graphdata['id']
    body_filename = '{0}.html'.format(slugify(graphdata.get('subject') or 'sem-assunto'))
    body_path = ensure_dir(dump_path / '__body__') / body_filename
    body_path.write_text(html_message(graphdata, True), encoding='utf-8')
    source_paths.append(body_path)
    for attachment in graphdata.get('attachments', []):
        att_filename = attachment.get('name')
        if not pathvalidate.is_valid_filename(att_filename):
            att_filename = pathvalidate.sanitize_filename(att_filename)
            if not splitext(att_filename)[1]:
                att_filename = att_filename + (mimetypes.guess_extension(attachment.get('contentType')) or '.bin')
            att_path = ensure_dir(dump_path / '__atts__') / att_filename
            att_path.write_bytes(base64.b64decode(attachment.get('contentBytes')))
            source_paths.append(att_path)
    target_paths: list[Path] = []
    for source_path in source_paths:
        target_paths.extend(converter_arquivo(source_path))
    return target_paths


def converter_unconvertible(file_path: Path = None, mimetype: str = None):
    if mimetype is None: mimetype = filetype.guess_mime(file_path)
    if mimetype is None: mimetype = mimetypes.guess_type(file_path)[0]
    warnings.warn(f"Conversão indisponível ou falhando para o arquivo {file_path} (tipo MIME: {mimetype})")
    path_html = Path(f'{splitext(file_path)[0]}.html')
    path_html.write_text(
        f'<!DOCTYPE html><html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head>'
        f'<body><h1>Anexo sem conversão</h1><p>Não foi possível converter o anexo abaixo em um formato legível '
        f'diretamente no navegador:</p><ul><li><strong>Nome:</strong>&nbsp;<em>{html_escape(file_path.name)}</em></li>'
        f'<li><strong>Tipo:</strong>&nbsp;<em>{html_escape(mimetype)}</em></li></ul><p>O sistema tentou anexar o '
        f'arquivo original a este PDF, para conferência. Use a ferramenta adequada de seu leitor de PDF para acessar o '
        f'arquivo acima indicado, se ele estiver presente.</p></html>',
        encoding='utf-8',
    )
    paths_pdf = converter_html(path_html)
    if paths_pdf:
        from pypdf import PdfReader, PdfWriter
        for path_pdf in paths_pdf:
            reader = PdfReader(path_pdf)
            writer = PdfWriter()
            writer.append_pages_from_reader(reader)
            writer.add_attachment(filename=file_path.name, data=file_path.read_bytes())
            writer.write(path_pdf)
    return paths_pdf
