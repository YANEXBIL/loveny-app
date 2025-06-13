# accounts/routing.py

from django.urls import re_path # Using re_path for regex-based URL patterns
from . import consumers # Import your ChatConsumer

websocket_urlpatterns = [
    # This pattern routes WebSocket connections to the ChatConsumer.
    # It expects a username in the URL (e.g., ws://localhost:8000/ws/chat/john_doe/)
    # The 'username' captured here will be available in the consumer's scope.
    re_path(r'ws/chat/(?P<username>\w+)/$', consumers.ChatConsumer.as_asgi()),
]
