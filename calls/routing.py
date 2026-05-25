"""WebSocket URL routing for the Horilla Calls Integration app."""

from horilla.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/calls/$", consumers.IncomingCallConsumer.as_asgi()),
]
