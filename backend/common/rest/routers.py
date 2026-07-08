import inspect
import re
import warnings
from types import ModuleType

from django.core.exceptions import ImproperlyConfigured
from rest_framework import permissions, routers, viewsets


class AutoRouter(routers.DefaultRouter):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.get_api_root_view().cls.permission_classes = [permissions.AllowAny]

    @staticmethod
    def _make_prefix(viewset):
        return re.sub('_view_set$', '', re.sub(r'(?<!^)(?=[A-Z])', '_', viewset.__name__).lower())

    def register_viewset_module(self, prefix: str, module: ModuleType):
        objects = {k: getattr(module, k) for k in dir(module) if not k.startswith('_')}
        _viewsets = {
            k: v for k, v in objects.items()
            if inspect.isclass(v) and issubclass(v, (viewsets.GenericViewSet, viewsets.ViewSet))
        }
        for viewset in _viewsets.values():
            vprefix = self._make_prefix(viewset)
            self.register(f'{prefix}/{vprefix}', viewset)
        return self

    def register_from_modules(self, modules: dict[str, ModuleType] = None, **kwargs):
        modules = (modules or {}) | {
            k: v for k, v in kwargs.items()
            if isinstance(k, str) and isinstance(v, ModuleType)
        }
        for prefix, module in modules.items():
            self.register_viewset_module(prefix, module)
        return self

    def get_default_basename(self, viewset):
        try:
            return super().get_default_basename(viewset)
        except AssertionError:
            return self._make_prefix(viewset)

    # noinspection PyMethodOverriding
    def register(self, prefix: str, viewset: type[viewsets.ViewSetMixin], basename: str | None = None) -> None:
        try:
            super().register(prefix, viewset, basename)
        except ImproperlyConfigured as ex:
            warnings.warn(f'{self.__class__.__qualname__}.register() raised ImproperlyConfigured exception:\n{ex}')
        except AssertionError:
            basename = prefix.split('/')[-1]
            super().register(prefix, viewset, basename)
