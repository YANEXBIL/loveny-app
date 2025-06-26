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
    path('accounts/', include('accounts.urls', namespace='accounts')), 
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    # Ensure STATIC_ROOT is used for static files, if collectstatic has been run
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

