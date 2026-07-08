from django.db import models
from rest_framework import serializers, viewsets


def build_serializer_class(model: type[models.Model]):
    class_name = f'{model.__name__}Serializer'
    meta_class = type('Meta', (), {'model': model, 'fields': '__all__'})
    class_attrs = {'Meta': meta_class}
    return type(class_name, (serializers.ModelSerializer,), class_attrs)


def build_viewset_class(
        model: type[models.Model],
        serializer: type[serializers.Serializer] = None,
        read_only: bool = False,
):
    class_name = f'{model.__name__}ViewSet'
    class_attrs = {
        'serializer_class': serializer or serializers.ModelSerializer,
        'queryset': model.objects.all(),
    }
    base_class = viewsets.ReadOnlyModelViewSet if read_only else viewsets.ModelViewSet
    return type(class_name, (base_class,), class_attrs)
