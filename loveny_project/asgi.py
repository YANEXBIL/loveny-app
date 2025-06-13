# loveny_project/asgi.py

import os

from channels.auth import AuthMiddlewareStack # For authenticating WebSocket connections
from channels.routing import ProtocolTypeRouter, URLRouter # For routing different protocols and URLs
from django.core.asgi import get_asgi_application

# Set the default Django settings module for the 'asgi' application.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'loveny_project.settings')

# Get Django's ASGI application for handling HTTP requests.
# This should be at the top to ensure Django's standard HTTP routing works.
# Note: get_asgi_application() can only be called once.
django_asgi_app = get_asgi_application()

# Import your application's WebSocket routing
# It's important to do this *after* get_asgi_application()
import accounts.routing

application = ProtocolTypeRouter(
    {
        # Django's ASGI application to handle traditional HTTP requests
        "http": django_asgi_app, # Use the already initialized django_asgi_app

        # WebSocket chat handler
        # AuthMiddlewareStack adds the 'user' attribute to the WebSocket scope,
        # allowing you to access request.user in your consumers.
        "websocket": AuthMiddlewareStack(
            URLRouter(
                accounts.routing.websocket_urlpatterns # Your WebSocket URL patterns
            )
        ),
    }
)
