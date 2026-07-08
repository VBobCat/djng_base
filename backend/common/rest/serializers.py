import json
from json import JSONDecodeError

from django.db import models
from O365.utils.casing import to_pascal_case
from rest_framework import serializers
from rest_framework.request import Request

from common.misc import getprop


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField(write_only=True)


class ShapeMixin:
    def __init__(self, *args, **kwargs):
        self.shape = kwargs.pop('shape', None)
        if not self.shape:
            request = kwargs.get('context', {}).get('request')
            if isinstance(request, Request):
                shape_param = request.query_params.get('shape', None)
                if shape_param:
                    try:
                        self.shape = json.loads(shape_param)
                    except JSONDecodeError:
                        self.shape = shape_param if isinstance(shape_param, str) else None
        super().__init__(*args, **kwargs)

    def get_fields(self):
        # noinspection PyUnresolvedReferences
        fields = super().get_fields()
        if isinstance(self.shape, str):
            self.shape = getattr(getattr(self, 'Meta', None), 'preset_shapes', {}).get(self.shape)
        if isinstance(self.shape, list) and all(isinstance(el, str) for el in self.shape):
            all_fields = '*' in self.shape
            shaped_fields = {}
            for k, v in fields.items():
                if all_fields or k in self.shape:
                    shaped_fields[k] = v
            for k, v in fields.items():
                xshape = [s[1 + len(k):] for s in self.shape if s.startswith(f'{k}.')]
                xmany = isinstance(v, serializers.ManyRelatedField)
                xmodel = v.child_relation.queryset.model if xmany else (
                    v.queryset.model if isinstance(v, serializers.RelatedField) else None
                )
                if xshape and xmodel:
                    xserializer_class = type(
                        f'{to_pascal_case(k)}ShapeSerializer',
                        (ShapeMixin, serializers.ModelSerializer),
                        {'Meta': type('Meta', (), {'model': xmodel, 'fields': '__all__'})},
                    )
                    shaped_fields[k] = xserializer_class(
                        read_only=v.read_only, write_only=v.write_only,
                        required=v.required, default=v.default, initial=v.initial, source=v.source,
                        label=v.label, help_text=v.help_text, style=v.style,
                        error_messages=v.error_messages, validators=v.validators, allow_null=v.allow_null,
                        shape=xshape, many=xmany,
                    )
            fields_map = getprop(self, 'Meta.model._meta.fields_map')
            if fields_map:
                for k, v in fields_map.items():
                    if not isinstance(v, models.ForeignObjectRel): continue
                    xshape = [s[1 + len(k):] for s in self.shape if s.startswith(f'{k}.')]
                    if not xshape: continue
                    xmodel = v.related_model
                    xserializer_class = type(
                        f'{to_pascal_case(k)}ShapeSerializer',
                        (ShapeMixin, serializers.ModelSerializer),
                        {'Meta': type('Meta', (), {'model': xmodel, 'fields': '__all__'})},
                    )
                    shaped_fields[k] = xserializer_class(read_only=True, many=v.one_to_many, shape=xshape)
            return shaped_fields
        return fields


class PasswordCharField(serializers.CharField):
    def __init__(self, **kwargs):
        kwargs.setdefault('min_length', 4)
        kwargs.setdefault('required', True)
        kwargs.setdefault('write_only', True)
        kwargs.setdefault('style', {})
        kwargs['style'].setdefault('input_type', 'password')
        super().__init__(**kwargs)
