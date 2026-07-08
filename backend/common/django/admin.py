import json
import logging

from django.apps import apps
from django.conf import settings
from django.contrib.admin import AdminSite, ModelAdmin
from django.contrib.admin.exceptions import AlreadyRegistered
from django.db import models
from django.forms import widgets

logger = logging.getLogger(__name__)

TABLE_VISIBLE_FIELD_TYPES = (
    models.CharField,
    models.IntegerField,
    models.DateField,
    models.BooleanField,
    models.ForeignKey
)
FILTERABLE_FIELD_TYPES = (models.CharField, models.IntegerField, models.DateField, models.BooleanField)
SEARCHABLE_FIELD_TYPES = (models.CharField, models.TextField)


class AtenaJSONWidget(widgets.Textarea):

    def format_value(self, value):
        try:
            value = json.dumps(json.loads(value), indent=2, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split('\n')]
            self.attrs['rows'] = min(max(len(row_lengths) + 2, 10), 30)
            self.attrs['cols'] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except Exception as e:
            logger.warning("Error while formatting JSON: {}".format(e))
            return super(AtenaJSONWidget, self).format_value(value)


class AtenaModelAdmin(ModelAdmin):
    formfield_overrides = {models.JSONField: {'widget': AtenaJSONWidget}}

    def __init__(self, model, admin_site):
        super().__init__(model, admin_site)
        self._dynamic_list_display = [
            f.name for f in model._meta.fields
            if isinstance(f, TABLE_VISIBLE_FIELD_TYPES)
        ]
        self._dynamic_list_filter = [
            f.name for f in model._meta.fields
            if isinstance(f, FILTERABLE_FIELD_TYPES) and not (f.primary_key or f.unique)
        ]
        self._dynamic_search_fields = [
            f.name for f in model._meta.fields
            if isinstance(f, SEARCHABLE_FIELD_TYPES)
        ]

    def get_list_display(self, request):
        return self._dynamic_list_display

    def get_list_filter(self, request):
        return self._dynamic_list_filter

    def get_search_fields(self, request):
        return self._dynamic_search_fields

    def get_form(self, request, obj=None, **kwargs):
        """Remove o campo 'is_superuser' do formulário se o usuário não for superusuário."""
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'is_superuser' in form.base_fields:
                form.base_fields.pop('is_superuser')
        return form

    def has_change_permission(self, request, obj=None):
        """Impede que um usuário comum consiga editar a conta de um superusuário existente."""
        # Se estamos editando um objeto específico que possui o atributo is_superuser = True
        if obj is not None and getattr(obj, 'is_superuser', False):
            # Se quem está logado não é superusuário, negamos a permissão
            if not request.user.is_superuser:
                return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        """Impede que um usuário comum consiga deletar a conta de um superusuário existente."""
        if obj is not None and getattr(obj, 'is_superuser', False):
            if not request.user.is_superuser:
                return False
        return super().has_delete_permission(request, obj)


class AtenaAdminSite(AdminSite):
    site_header = 'Administração do Atena'

    def __init__(self, *, extra_apps: list[str] | None = None):
        super().__init__('Atena admin')
        app_names = set(settings.PROJECT_APPS)
        if extra_apps:
            for extra_app_name in extra_apps:
                app_names.add(extra_app_name)
        for app_name in sorted(app_names):
            for model in apps.get_app_config(app_name).get_models():
                try:
                    self.register(model, AtenaModelAdmin)
                except AlreadyRegistered:
                    pass
