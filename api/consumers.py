import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder

from api.exceptions import SimpleWishlistValidationError
from api.pydantic_models import WishModelUpdate, WishListUserModel, WebhookPayloadModel
from api.utils import update_wish
from core.models import WishListUser


class WishlistConsumer(JsonWebsocketConsumer):
    current_user = None
    wishlist = None

    def connect(self):
        """On connect, we get the user from the URL and join the group with the wishlist id"""
        # If the user is not found, we close the connection
        try:
            self.current_user = WishListUser.objects.get(pk=self.scope["url_route"]["kwargs"]["wishlist_user"])
        except WishListUser.DoesNotExist:
            self._send(json.dumps({"type": "error_message", "data": "User not found"}))
            self.close()

        self.wishlist = self.current_user.wishlist

        self.room_group_name = f"wishlist_{self.wishlist.id}"

        # Join room group
        async_to_sync(self.channel_layer.group_add)(self.room_group_name, self.channel_name)

        self.accept()

    def disconnect(self, close_code):
        """On disconnect, we leave the group"""
        async_to_sync(self.channel_layer.group_discard)(self.room_group_name, self.channel_name)

    def receive_json(self, content: dict, **kwargs):
        """Receive a message from the group and process it"""

        try:
            # Validate the payload
            payload = WebhookPayloadModel.model_validate(content)

            # Dynamically call the method based on the payload type
            # I.e : if the payload type is "assign_wish", we call the assign_wish method
            action_method = getattr(self, payload.type)

            action_method(payload)

        except SimpleWishlistValidationError as e:
            self._send(json.dumps({"type": "error_message", "data": str(e)}))
        except Exception as e:
            self._send(json.dumps({"type": "error_message", "data": str(e)}))

    # ACTIONS
    def assign_wish(self, payload: WebhookPayloadModel):
        """Assign a wish to a user and send the updated wishes to the group"""
        wish_payload = WishModelUpdate.model_validate(payload.post_values)

        # Update the wish
        update_wish(self.current_user, payload.objectId, wish_payload)

        # Send the updated wishes to the groups
        users = self.wishlist.get_active_users()
        users_wishes = []
        for user in users:
            wishes = user.get_user_wishes()
            users_wishes.append(
                WishListUserModel(
                    user=user.name,
                    wishes=wishes,
                ).dict()
            )

        self.send_group_message("update_wishes", users_wishes)

    # RESPONSES
    def send_group_message(self, type: str, data: dict | list | str):
        """
        Send a message to the group with the given type and data
        The type is the name of the method to call in the consumer
        """
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {
                "type": type,
                "data": data,
            },
        )

    def _send(self, event: dict):
        self.send_json(content=json.dumps(event, cls=DjangoJSONEncoder))

    def update_wishes(self, event: dict):
        self._send(event)

    def error_message(self, event: dict):
        self._send(event)
