import json

from django.db import models
from rest_framework import compat, exceptions, filters


class JsonParameterFilterBackend(filters.BaseFilterBackend):

    def filter_param_to_q(self, filter_param):
        if not filter_param:
            return None
        filter_object = json.loads(filter_param)
        return self.filter_object_to_q(filter_object)

    @staticmethod
    def order_by_param_to_list(order_by_param):
        if not order_by_param:
            return None
        try:
            order_by_list = json.loads(order_by_param)
        except (TypeError, ValueError):
            order_by_list = order_by_param.split(',')
        order_by_list = [o.replace('.', '__') for o in order_by_list]
        if not (isinstance(order_by_list, list) and all(isinstance(x, str) for x in order_by_list)):
            raise exceptions.ParseError()
        return order_by_list

    def filter_object_to_q(self, filter_object: dict):
        q = models.Q()
        for parameter, value in filter_object.items():
            if parameter in ('|', '&', '||', '&&'):
                if not (isinstance(value, list) and all(isinstance(x, dict) for x in value)):
                    raise exceptions.ParseError()
                subq = models.Q()
                for subfilter_object in value:
                    if parameter in ('|', '||'):
                        subq |= self.filter_object_to_q(subfilter_object)
                    elif parameter in ('&', '&&'):
                        subq &= self.filter_object_to_q(subfilter_object)
                q &= subq
            else:
                q &= models.Q(**{parameter.replace('.', '__').replace(' ', '__'): value})
        return q

    def filter_queryset(self, request, queryset: models.QuerySet, view):
        for queryparamkey in request.query_params.keys():
            try:
                if queryparamkey not in ('filter', 'exclude', 'order_by'): continue
                for queryparamvalue in request.query_params.getlist(queryparamkey):
                    if not queryparamvalue: continue
                    if queryparamkey == 'filter':
                        filter_q = self.filter_param_to_q(queryparamvalue)
                        if filter_q:
                            queryset = queryset.filter(filter_q)
                    elif queryparamkey == 'exclude':
                        exclude_q = self.filter_param_to_q(queryparamvalue)
                        if exclude_q:
                            queryset = queryset.exclude(exclude_q)
                    elif queryparamkey == 'order_by':
                        order_by_list = self.order_by_param_to_list(queryparamvalue)
                        if order_by_list:
                            queryset = queryset.order_by(*order_by_list)
            except Exception as e:
                raise exceptions.ParseError(
                    detail={queryparamkey: 'Expressão inválida causou {0}: {1}'.format(e.__class__.__name__, *e.args)},
                )
        return queryset

    def get_schema_fields(self, view):
        return [compat.coreapi.Field(name='filter'), compat.coreapi.Field(name='order_by')]
