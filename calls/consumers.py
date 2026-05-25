"""WebSocket consumers for real-time incoming call notifications."""

import json

from channels.generic.websocket import AsyncWebsocketConsumer


class IncomingCallConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time incoming call popups.

    Each authenticated user connects to the group "calls_{user_id}".
    When an inbound call arrives via webhook, the system pushes to the
    matched agent's group so a popup appears in their browser instantly.
    """

    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        self.group_name = f"calls_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def incoming_call(self, event):
        """
        Called by group_send with type='incoming_call'.
        Forwards the payload to the connected browser.
        """
        await self.send(
            text_data=json.dumps(
                {
                    "type": "incoming_call",
                    "from_number": event["from_number"],
                    "to_number": event["to_number"],
                    "provider_name": event["provider_name"],
                    "call_log_id": event["call_log_id"],
                    "related_name": event.get("related_name"),
                }
            )
        )
