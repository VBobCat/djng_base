import base64
import random
import zoneinfo
from datetime import datetime
from email import header, message, parser, policy, utils
from html import escape as html_escape
from pathlib import Path
from typing import Iterable, Literal

import babel.dates as babel_dates
import regex
from bs4 import BeautifulSoup, Doctype
from django.conf import settings

from common.typing.coerce import Coerce


def graph_datetime(dt):
    return dt.astimezone(zoneinfo.ZoneInfo('UTC')).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def decode_email_header(eml_header):
    decoded_header = header.decode_header(eml_header)
    decoded_str = ""
    for header_part, encoding in decoded_header:
        try:
            header_part = header_part.decode(encoding if encoding else 'utf-8', 'ignore')
        except AttributeError:
            pass
        decoded_str += header_part
    return decoded_str.strip()


def generate_graph_id(_type: Literal['msg', 'att']):
    return base64.urlsafe_b64encode(random.randbytes({'msg': 51, 'att': 72}[_type])).decode('ascii')


def format_recipient(recipient: dict, default: str = ''):
    if not recipient or not isinstance(recipient, dict): return default
    if 'emailAddress' in recipient: recipient = recipient['emailAddress']
    address = recipient.get('address')
    if not address: return default
    name = recipient.get('name')
    if not name or name == address: return address
    return f'{name} <{address}>'


def format_recipients(recipients: Iterable[dict], default: str = '', sep: str = '; '):
    if not recipients: return default
    return sep.join(format_recipient(recipient, default) for recipient in recipients) or default


def parse_recipient(recipient_str: str):
    recipient_str = str(recipient_str or '').strip()
    rx = regex.compile(
        r"(?:[-!#-'*+/-9=?A-Z^-~]+(?:\.[-!#-'*+/-9=?A-Z^-~]+)*|\"(?:[]!#-[^-~ \t]|(?:\\[\t -~]))+\")"
        r"@(?:[-!#-'*+/-9=?A-Z^-~]+(?:\.[-!#-'*+/-9=?A-Z^-~]+)*|\[[\t -Z^-~]*])"
    )
    address = next(iter(rx.findall(recipient_str)), '')
    name = next(iter(rx.split(recipient_str)), '').lstrip().rstrip(' <[{')
    return {'emailAddress': {'address': address, 'name': name}} if address else None


def email_to_graphdata(eml_path: Path):
    eml_parser = parser.BytesParser(message.EmailMessage, policy=policy.default)
    with eml_path.open('rb') as eml_file:
        eml_message = eml_parser.parse(eml_file)
    received_header_values = eml_message.get_all('received', [])
    formatted_received_datetimes = []
    for value in received_header_values:
        try:
            dt = utils.parsedate_to_datetime(value.split(';')[-1])
        except ValueError:
            continue
        formatted_received_datetimes.append(graph_datetime(dt))
    format_received_datetime = formatted_received_datetimes[0] if formatted_received_datetimes else None
    formatted_sent_datetime = graph_datetime(
        utils.parsedate_to_datetime(decode_email_header(_dtheader))
    ) if isinstance(_dtheader := eml_message.get('date'), str) else None
    graphdata: dict[str, str | None | list | dict[str, str] | list[dict[str, str | None]]] = {
        'id': generate_graph_id('msg'),
        'subject': decode_email_header(eml_message.get('Subject', '')),
        'sentDateTime': formatted_sent_datetime,
        'receivedDateTime': format_received_datetime,
        'from': parse_recipient(decode_email_header(eml_message.get('From', ''))),
        'sender': parse_recipient(decode_email_header(eml_message.get('Sender', ''))),
        'toRecipients': [parse_recipient(decode_email_header(value)) for value in eml_message.get_all('To', [])],
        'ccRecipients': [parse_recipient(decode_email_header(value)) for value in eml_message.get_all('CC', [])],
        'bccRecipients': [parse_recipient(decode_email_header(value)) for value in eml_message.get_all('BCC', [])],
        'replyTo': [parse_recipient(decode_email_header(value)) for value in eml_message.get_all('reply_to', [])],
        'body': {'content': '', 'contentType': 'text'},
        'attachments': [],
        'internetMessageHeaders': [{'name': name, 'value': value} for name, value in eml_message.items()]
    }
    for part in eml_message.walk():
        content_type = part.get_content_type()
        charset = part.get_content_charset() or 'utf-8'
        if content_type == 'text/plain' and not graphdata['body']['content']:  # Parse email text body if no html found
            payload = part.get_payload(decode=True)
            graphdata['body']['content'] = payload.decode(charset, 'ignore')
            graphdata['body']['contentType'] = 'text'
        elif content_type == 'text/html':  # Parse email html body
            payload = part.get_payload(decode=True)
            graphdata['body']['content'] = payload.decode(charset, 'ignore')
            graphdata['body']['contentType'] = 'html'
        if part.get('Content-Disposition'):  # Extract attachments
            content_bytes = part.get_payload(decode=True)
            if not content_bytes: continue
            attachment = {
                'id': generate_graph_id('att'),
                'isInline': 'inline' in part['Content-Disposition'],
                'name': decode_email_header(part.get_filename('')),
                'contentType': content_type,
                'contentId': part.get('Content-ID', ''),
                'lastModifiedDateTime': None,
                'contentBytes': base64.b64encode(content_bytes).decode('ascii'),
                'size': len(content_bytes),
            }
            graphdata['attachments'].append(attachment)
    return graphdata


cast_to_datetime = Coerce.as_datetime


def format_datetime_as_localized_full(datetime_value, default=''):
    if not type(datetime_value) is datetime:
        datetime_value = cast_to_datetime(datetime_value)
    if not datetime_value: return default
    return babel_dates.format_datetime(datetime_value, 'full', locale=settings.LANGUAGE_CODE.replace('-', '_'))


def info_table_mensagem(message_dict: dict):
    enviado_em = format_datetime_as_localized_full(message_dict.get('sentDateTime'))
    de = html_escape(format_recipient(message_dict.get('from', message_dict.get('sender')), '-'))
    para = html_escape(format_recipients(message_dict.get('toRecipients'), '-'))
    cc = html_escape(format_recipients(message_dict.get('ccRecipients'), '-'))
    assunto = html_escape(str(message_dict.get('subject') or '').strip() or '(sem assunto)')
    anexos = '<br>'.join(
        f'<span data-att-id="{att["id"]}" >{html_escape(att["name"])}</span>'
        for att in message_dict.get('attachments', [])
        if not att['isInline']
    ) or '-'
    cabecalhos = ''.join(
        f"<tr hidden=\"hidden\" style=\"display: none\"><th>{html_escape(imh['name'])}</th><td>"
        f"{html_escape(imh['value'])}</td></tr>"
        for imh in message_dict.get('internetMessageHeaders', [])
    )
    tstyle = 'background-color:white;width:100%;border:2px solid orange;border-collapse:collapse;margin-bottom:12px;'
    cstyle = 'border:1px solid orange;padding:3px 6px;text-align:justify;'
    table_html = (
        f'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head><body>'
        f'<table class="atena-message-infotable" style="{tstyle}"><thead><tr><th colspan="2" scope="col" '
        f'style="padding: 6px 12px">'
        f'<span style="font-size: larger">&#x2709; Mensagem de Correio Eletr&ocirc;nico</span>'
        f'</th></tr></thead><tbody>'
        f'<tr><th style="{cstyle} scope="row">Enviado em</th><td style="{cstyle}">{enviado_em}</td></tr>'
        f'<tr><th style="{cstyle} scope="row">De</th><td style="{cstyle}">{de}</td></tr>'
        f'<tr><th style="{cstyle} scope="row">Para</th><td style="{cstyle}">{para}</td></tr>'
        f'<tr><th style="{cstyle} scope="row">CC</th><td style="{cstyle}">{cc}</td></tr>'
        f'<tr><th style="{cstyle} scope="row">Assunto</th><td style="{cstyle}">{assunto}</td></tr>'
        f'<tr><th style="{cstyle} scope="row">Anexos</th><td style="{cstyle}">{anexos}</td></tr>'
        f'{cabecalhos}'
        f'</tbody></table></body></html>'
    )
    return BeautifulSoup(table_html, 'lxml')


def html_message(message_dict: dict, info_table: bool = False):
    body = message_dict.get('body', {})
    btype = body.get('contentType', 'text')
    bdata = body.get('content', '')
    if btype == 'text' or not bdata:
        bdata = (f'<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"></head><body><pre>'
                 f'{bdata}</pre></html>')
    soup = BeautifulSoup(bdata, 'lxml')
    for img in soup.select('img'):
        src = img.get('src', '')
        if src.startswith('cid:'):
            att = next((att for att in message_dict.get('attachments', []) if att.get('contentId') == src[4:]), None)
            if att and 'contentBytes' in att and att['size'] <= 5242880:
                img['src'] = 'data:{contentType};base64,{contentBytes}'.format(**att)
                att['embeddedAsImgSrc'] = True
        else:
            img['referrerpolicy'] = 'same-origin'
    if info_table:
        soup.body.insert(0, info_table_mensagem(message_dict).table)
        if not any(isinstance(item, Doctype) for item in soup.contents):
            soup.insert(0, Doctype('html'))
    return soup.decode(formatter='html5')
