from rest_framework import decorators, generics, permissions, response as rest_response, viewsets
from rest_framework.response import Response


class ViewSetShapeMixin(viewsets.GenericViewSet):
    # serializer_class = None
    # serializer_meta: dict = None
    #
    # def __init_subclass__(cls, **kwargs):
    #     print('ViewSetShapeMixin.__init_subclass__', cls, kwargs)
    #     super().__init_subclass__(**kwargs)
    #     if not getattr(cls, 'serializer_class', None):
    #         model = getattr(getattr(cls, 'queryset', None), 'model', None)
    #         if model:
    #             kwargs = cls.serializer_meta if isinstance(cls.serializer_meta, dict) else {}
    #             cls.serializer_class = ModelSerializer.from_model(model, **kwargs)

    @decorators.action(methods=('GET',), detail=False)
    def count(self, _request, *_args, **_kwargs):
        return rest_response.Response(self.get_queryset().count())


class ModelViewSet(ViewSetShapeMixin, viewsets.ModelViewSet):
    pass


class ReadOnlyModelViewSet(ViewSetShapeMixin, viewsets.ReadOnlyModelViewSet):
    pass


class CustomActionsViewSet(viewsets.mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = None

    def list(self, request, *args, **kwargs):
        return rest_response.Response(self.get_extra_action_url_map())


class ActionsViewSet(generics.GenericAPIView, viewsets.ViewSet):
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = None

    def list(self, _request):
        return Response(self.get_extra_action_url_map())
