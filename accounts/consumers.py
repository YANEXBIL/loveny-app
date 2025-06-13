# accounts/consumers.py

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string # For rendering message HTML
from asgiref.sync import sync_to_async # Helper for running sync Django ORM in async consumer

# Get the custom UserProfile model
UserProfile = get_user_model()

# Import your Conversation and Message models
from .models import Conversation, Message

class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for handling real-time chat messages.
    """

    async def connect(self):
        """
        Called when a WebSocket connection is established.
        Authenticates the user and joins them to a specific chat room group.
        """
        self.other_username = self.scope['url_route']['kwargs']['username']
        self.user = self.scope['user'] # The currently authenticated user

        print(f"CONNECT: User '{self.user.username}' attempting to connect to chat with '{self.other_username}'")

        # Reject connection if the user is not authenticated
        if not self.user.is_authenticated:
            print(f"CONNECT: User NOT authenticated. Closing connection for '{self.user}'.")
            await self.close()
            return

        # Get the other user's profile
        try:
            self.other_user = await sync_to_async(get_object_or_404)(UserProfile, username=self.other_username)
            print(f"CONNECT: Found other user: '{self.other_user.username}'")
        except Exception as e:
            # If the other user doesn't exist, close the connection
            print(f"CONNECT: Other user '{self.other_username}' not found. Error: {e}. Closing connection.")
            await self.close()
            return

        # Ensure the conversation is between two distinct users
        if self.user.id == self.other_user.id:
            print(f"CONNECT: User attempting to chat with self. Closing connection for '{self.user.username}'.")
            await self.close() # Cannot chat with self
            return

        # Find or create the conversation between the two users
        self.conversation, created = await sync_to_async(Conversation.get_or_create_conversation)(
            self.user, self.other_user
        )
        print(f"CONNECT: Conversation ID: {self.conversation.id}, Created: {created}")


        self.room_group_name = f'chat_{self.conversation.id}'
        print(f"CONNECT: Joining room group '{self.room_group_name}' for user '{self.user.username}'")

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept() # Accept the WebSocket connection
        print(f"CONNECT: WebSocket connection ACCEPTED for user '{self.user.username}'.")


    async def disconnect(self, close_code):
        """
        Called when a WebSocket connection is disconnected.
        Removes the user's channel from the chat group.
        """
        print(f"DISCONNECT: User '{self.user.username}' disconnecting from group '{self.room_group_name}'. Close code: {close_code}")
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        """
        Called when a message is received from the WebSocket.
        Parses the message, saves it to the database, and broadcasts it to the group.
        """
        print(f"RECEIVE: Message received from '{self.user.username}': {text_data}")
        try:
            text_data_json = json.loads(text_data)
            message_content = text_data_json.get('message', '').strip() # Use .get() and .strip() for safety
            print(f"RECEIVE: Parsed message content: '{message_content}'")

            if not message_content: # Don't process empty messages
                print("RECEIVE: Empty message content. Ignoring.")
                return

            # Save the message to the database asynchronously
            message = await sync_to_async(Message.objects.create)(
                conversation=self.conversation,
                sender=self.user,
                content=message_content
            )
            print(f"RECEIVE: Message saved to DB (ID: {message.id}).")

            # Render the message as HTML (for display in the chat UI)
            rendered_message_html = await sync_to_async(render_to_string)(
                'accounts/partials/message.html',
                {'message': message, 'current_user': self.user}
            )
            print(f"RECEIVE: Message rendered to HTML.")

            # Send message to room group (broadcast to all connected clients in this conversation)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message', # This calls the chat_message method below
                    'message_html': rendered_message_html,
                    'sender_username': self.user.username,
                    'timestamp': message.timestamp.isoformat()
                }
            )
            print(f"RECEIVE: Message broadcasted to group '{self.room_group_name}'.")

        except json.JSONDecodeError:
            print(f"RECEIVE ERROR: Could not decode JSON from message: {text_data}")
        except Exception as e:
            print(f"RECEIVE ERROR: An unexpected error occurred in receive method: {e}")


    async def chat_message(self, event):
        """
        Called when a message is received from the channel layer.
        Sends the message HTML directly to the WebSocket.
        """
        message_html = event['message_html']
        sender_username = event['sender_username']
        timestamp = event['timestamp']

        print(f"CHAT_MESSAGE: Sending message from '{sender_username}' to WebSocket.")
        # Send the rendered HTML message to the WebSocket
        await self.send(text_data=json.dumps({
            'message_html': message_html,
            'sender_username': sender_username,
            'timestamp': timestamp
        }))
