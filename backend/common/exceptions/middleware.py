from .logger import save_exception_traceback


class UnhandledExceptionLoggingMiddleware:
    """
    Middleware que captura exceções não tratadas,
    registra informações completas do request e
    repropaga o erro.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as exc:
            save_exception_traceback(exc, request)
            raise
