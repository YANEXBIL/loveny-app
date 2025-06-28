# loveny_project/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings # Import settings
from django.conf.urls.static import static # Import static
from django.views.generic.base import RedirectView # Import RedirectView

urlpatterns = [
    # Redirect root URL to the accounts homepage
    path('', RedirectView.as_view(pattern_name='accounts:homepage', permanent=False), name='home'),
    path('admin/', admin.site.urls),
    # Include accounts.urls under the 'accounts/' prefix
    # Removed redundant namespace='accounts' as app_name is already set in accounts/urls.py
    path('accounts/', include('accounts.urls')), 
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # In DEBUG mode, Django's staticfiles app serves static files automatically
    # from STATICFILES_DIRS and app 'static' folders.
    # Serving from STATIC_ROOT is typically for production deployments after collectstatic.
    # So, removed: urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)