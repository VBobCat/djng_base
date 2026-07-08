from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer, Serializer
from rest_framework.status import HTTP_200_OK
from rest_framework.viewsets import ViewSet
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.serializers import (
    TokenObtainSlidingSerializer,
    TokenRefreshSlidingSerializer,
    TokenVerifySerializer,
)
from rest_framework_simplejwt.views import TokenViewBase


class AuthViewSet(ViewSet, TokenViewBase):
    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.action == "get_token":
            return TokenObtainSlidingSerializer
        elif self.action == "refresh_token":
            return TokenRefreshSlidingSerializer
        elif self.action == "verify_token":
            return TokenVerifySerializer
        else:
            return Serializer

    def _dispatch(self, request: Request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0]) from e
        return Response(serializer.validated_data, status=HTTP_200_OK)

    def list(self, *_, **__):
        return Response(self.get_extra_action_url_map())

    @action(detail=False, methods=['POST'])
    def get_token(self, request, *args, **kwargs):
        return self._dispatch(request, *args, **kwargs)

    @action(detail=False, methods=['POST'])
    def refresh_token(self, request, *args, **kwargs):
        return self._dispatch(request, *args, **kwargs)

    @action(detail=False, methods=['POST'])
    def verify_token(self, request, *args, **kwargs):
        return self._dispatch(request, *args, **kwargs)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        delattr(self, 'post')
