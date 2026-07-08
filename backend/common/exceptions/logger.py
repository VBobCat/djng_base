import traceback
from datetime import datetime

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from ipware import get_client_ip


def serialize_headers(request: HttpRequest) -> dict:
    return {
        key: value for key, value in request.META.items()
        if key.startswith("HTTP_") or key in ("CONTENT_TYPE", "CONTENT_LENGTH")
    }


def write_logfile(
    origin: str,
    request: HttpRequest,
    error_info: str,
    user: str,
):
    now = datetime.now()
    month_dir = settings.MEDIA_ROOT / 'logs' / now.strftime("%Y%m")
    month_dir.mkdir(parents=True, exist_ok=True)
    file_path = month_dir / f"{now.strftime('%Y%m%d%H%M%S')}_{origin}.log"
    ip_address, routable_ip = get_client_ip(request)
    headers = serialize_headers(request)
    with file_path.open("w", encoding="utf-8") as f:
        f.write("==== LOG DE EXCEÇÃO ====\n\n")

        f.write(f"Timestamp : {now.isoformat()}\n")
        f.write(f"Caminho   : {request.path}\n")
        f.write(f"Método    : {request.method}\n")
        f.write(f"IP        : {ip_address or 'DESCONHECIDO'} ({'' if routable_ip else 'not'} routable)\n")
        f.write(f"User      : {user}\n\n")

        f.write("---- CABEÇALHOS ----\n")
        for key, value in headers.items():
            f.write(f"{key}: {value}\n")

        f.write("\n---- TRACEBACK / ERROR INFO ----\n")
        f.write(error_info)
    return file_path


def save_exception_traceback(exc: Exception, request: HttpRequest) -> None:
    user = (
        f"{request.user} (id={request.user.id})"
        if hasattr(request, "user") and request.user.is_authenticated
        else "Anônimo"
    )
    traceback_content = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    write_logfile('backend', request, traceback_content, user)


def save_exception_notice(request: HttpRequest):
    if request.method != 'POST':
        return JsonResponse(f'', status=405)
    user = (
        f"{request.user} (id={request.user.id})"
        if hasattr(request, "user") and request.user.is_authenticated
        else "Anônimo"
    )
    error_info = request.body.decode('utf-8')
    file_path = write_logfile('frontend', request, error_info, user)
    return JsonResponse({'log': file_path.stem}, status=201)
