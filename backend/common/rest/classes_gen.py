import os
import re

from django.apps import apps
from django.conf import settings

__all__ = ["generate_classes"]


def _to_snake_case(name):
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def _generate_serializer(model):
    return f"""from rest_framework import serializers
from {model._meta.app_label}.models import {model.__name__}

class {model.__name__}Serializer(ShapeMixin, serializers.ModelSerializer):
    class Meta:
        model = {model.__name__}
        fields = '__all__'
"""


def _generate_viewset(model, read_only: bool = False):
    read_only_prefix = 'ReadOnly' if read_only else ''
    return f"""from rest_framework import viewsets
from {model._meta.app_label}.models import {model.__name__}
from {model._meta.app_label}.serializers.{_to_snake_case(model.__name__)}_serializer import {model.__name__}Serializer

class {model.__name__}ViewSet(viewsets.{read_only_prefix}ModelViewSet):
    queryset = {model.__name__}.objects.all()
    serializer_class = {model.__name__}Serializer
"""


def _ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)
    init_file = os.path.join(path, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("")


def _is_local_app(app_config):
    return os.path.commonpath([settings.BASE_DIR]) in os.path.commonpath([settings.BASE_DIR, app_config.path])


def generate_classes(*app_names, read_only: bool = False):
    app_names = [str(app_name).casefold() for app_name in app_names]
    for app_config in apps.get_app_configs():
        if app_config.name.casefold() not in app_names:
            continue

        if not _is_local_app(app_config):
            continue

        models = app_config.get_models()
        if not models:
            continue

        serializers_dir = os.path.join(app_config.path, "serializers")
        viewsets_dir = os.path.join(app_config.path, "viewsets")

        _ensure_dir(serializers_dir)
        _ensure_dir(viewsets_dir)

        for model in models:
            serializer_filename = f"{_to_snake_case(model.__name__)}_serializer.py"
            viewset_filename = f"{_to_snake_case(model.__name__)}_viewset.py"

            serializer_file = os.path.join(serializers_dir, serializer_filename)
            viewset_file = os.path.join(viewsets_dir, viewset_filename)

            if not os.path.exists(serializer_file):
                serializer_code = _generate_serializer(model)
                with open(serializer_file, "w") as serializer_file:
                    serializer_file.write(serializer_code)
                    print(serializer_file.name)

            if not os.path.exists(viewset_file):
                viewset_code = _generate_viewset(model, read_only=read_only)
                with open(viewset_file, "w") as viewset_file:
                    viewset_file.write(viewset_code)
                    print(viewset_file.name)
