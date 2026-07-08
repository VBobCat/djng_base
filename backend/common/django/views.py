from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache


@method_decorator(never_cache, name='index')
class SpaStaticServer:
    def __init__(self, *, default_redirect: str = None):
        self.default_redirect = default_redirect
        from django.conf import settings
        from whitenoise.middleware import WhiteNoiseMiddleware
        self.whitenoise = WhiteNoiseMiddleware(settings=settings)
        if self.whitenoise.autorefresh:
            self.static_file = self.whitenoise.find_file('/')
        else:
            self.static_file = self.whitenoise.files.get('/')

    def index(self, request):
        from django.http import Http404
        if request.method == 'GET' and self.static_file is not None:
            return self.whitenoise.serve(self.static_file, request)
        if self.default_redirect:
            return redirect(self.default_redirect, permanent=False)
        raise Http404()
