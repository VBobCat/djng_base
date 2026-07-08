from django.contrib.auth.models import User
from django.utils.module_loading import import_string
from rest_framework import decorators, permissions, serializers, viewsets
from rest_framework.response import Response
from rest_framework_simplejwt.state import api_settings
from rest_framework_simplejwt.views import TokenObtainSlidingView, TokenRefreshSlidingView, TokenVerifyView

from sapiens_app.models import Usuario


class AuthViewSet(viewsets.GenericViewSet):
    class UserSerializer(serializers.ModelSerializer):
        class Meta:
            model = User
            fields = ['id', 'username', 'first_name', 'last_name', 'email', 'usuario_sapiens']

        class UsuarioSerializer(serializers.ModelSerializer):
            class Meta:
                model = Usuario
                fields = ['id', 'username', 'nome', 'email', 'nivelAcesso', 'roles']

        usuario_sapiens = serializers.SerializerMethodField(read_only=True)

        def get_usuario_sapiens(self, user):
            usuario = user.elo_usuario.usuario
            return self.UsuarioSerializer(instance=usuario).data if usuario else None

    permission_classes = [permissions.AllowAny]

    _obtain = TokenObtainSlidingView.as_view()
    _refresh = TokenRefreshSlidingView.as_view()
    _verify = TokenVerifyView.as_view()
    _serializers = {
        'get_token': import_string(api_settings.SLIDING_TOKEN_OBTAIN_SERIALIZER),
        'refresh_token': import_string(api_settings.SLIDING_TOKEN_REFRESH_SERIALIZER),
        'verify_token': import_string(api_settings.TOKEN_VERIFY_SERIALIZER),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_queryset(self):
        return User.objects.filter(pk=self.request.user.pk)

    def get_serializer_class(self):
        return self._serializers.get(self.action, self.UserSerializer)

    def list(self, request, *args, **kwargs):
        return Response(self.get_extra_action_url_map())

    @decorators.action(detail=False, methods=['GET'])
    def user(self, request, *args, **kwargs):
        self.kwargs['pk'] = request.user.pk
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @decorators.action(detail=False, methods=['POST'])
    def get_token(self, request, *args, **kwargs):
        return self.__class__._obtain(request._request, *args, **kwargs)

    @decorators.action(detail=False, methods=['POST'])
    def refresh_token(self, request, *args, **kwargs):
        return self.__class__._refresh(request._request, *args, **kwargs)

    @decorators.action(detail=False, methods=['POST'])
    def verify_token(self, request, *args, **kwargs):
        return self.__class__._verify(request._request, *args, **kwargs)
