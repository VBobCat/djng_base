from django.contrib import admin
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from health_check.views import HealthCheckView

from common.django.views import SpaStaticServer
from common.rest import routers

import core.views as core

static_server = SpaStaticServer(default_redirect='api/')

api = routers.AutoRouter()
api.register('core/auth',core.AuthViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(api.urls)),
    path('api/schema/', SpectacularAPIView.as_view(), name='api_schema'),
    path('api/doc/', SpectacularSwaggerView.as_view(url_name='api_schema'), name='swagger-ui'),
    path('api/auth_session/', include('rest_framework.urls')),
    path('health_check', HealthCheckView.as_view()),
    re_path(r'^(?!(?:admin|api|core)(?:$|[/?]))', static_server.index),

]
