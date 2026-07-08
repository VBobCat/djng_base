from pathlib import Path

from django.conf import settings
from gotenberg_client import GotenbergClient

HOST_URL = settings.GOTENBERG_URL


def html_to_pdf(input_file_path: Path):
    with GotenbergClient(HOST_URL) as client:
        with client.chromium.html_to_pdf() as route:
            return route.index(input_file_path).run()


def office_to_pdf(input_file_path: Path):
    with GotenbergClient(HOST_URL) as client:
        with client.libre_office.to_pdf() as route:
            return route.convert(input_file_path).run()
