from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('django-admin/', admin.site.urls),
    path('', include('pwa.urls')),
    path('', include('core.urls')),
    path('accounts/', include('accounts.urls')),
    path('farm/', include('farms.urls')),
    path('cows/', include('cows.urls')),
    path('crops/', include('crops.urls')),
    path('finance/', include('finance.urls')),
    path('inventory/', include('inventory.urls')),
    path('analysis/', include('analysis.urls')),
    path('notifications/', include('notifications.urls')),
    path('tasks/', include('tasks.urls')),
    path('weather/', include('weather.urls')),
    path('advisory/', include('advisory.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
