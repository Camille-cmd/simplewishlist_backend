import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import JsonWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.shortcuts import get_object_or_404

from api.exceptions import SimpleWishlistValidationError
from api.pydantic_models import WishModelUpdate, WebhookPayloadModel, WishModel
from api.utils import get_all_users_wishes, do_update_wish, get_wishlist_data
from core.models import WishListUser, Wish


class WishlistConsumer(JsonWebsocketConsumer):
    current_user = None
    wishlist = None

    def connect(self):
        """On connect, we get the user from the URL and join the group with the wishlist id"""
        # If the user is not found, we close the connection
        try:
            self.current_user = WishListUser.objects.get(pk=self.scope["url_route"]["kwargs"]["wishlist_user"])
        except WishListUser.DoesNotExist:
            self.send_individual_message({"type": "error_message", "data": "User not found"})
            self.close()

        self.wishlist = self.current_user.wishlist

        self.room_group_name = f"wishlist_{self.wishlist.id}"

        # Join room group
        async_to_sync(self.channel_layer.group_add)(self.room_group_name, self.channel_name)

        self.accept()

    def disconnect(self, close_code):
        """On disconnect, we leave the group"""
        # async_to_sync(self.channel_layer.group_discard)(self.room_group_name, self.channel_name)

    def receive_json(self, content: dict, **kwargs):
        """Receive a message from the group and process it"""

        try:
            # Validate the payload
            payload = WebhookPayloadModel.model_validate(content)

            match payload.type:
                case "wishlist_data":
                    self.get_wishlist_data()
                case "update_wish":
                    self.update_wish(payload)
                case "create_wish":
                    self.create_wish(payload)
                case "delete_wish":
                    self.delete_wish(payload)
                case _:
                    self.send_individual_message({"type": "error_message", "data": "Invalid action"})

        except SimpleWishlistValidationError as e:
            self.send_individual_message({"type": "error_message", "data": str(e)})
        except Exception as e:
            self.send_individual_message({"type": "error_message", "data": str(e)})

    # ACTIONS
    def get_wishlist_data(self):
        """Get the wishlist data and send it to the user"""
        data = get_wishlist_data(self.current_user)

        self.send_individual_message(
            {
                "type": "wishlist_data",
                "data": data.dict(),
                "userToken": self.current_user.name,
                "action": "get_wishlist_data",
            }
        )

    def update_wish(self, payload: WebhookPayloadModel):
        """Assign a wish to a user and send the updated wishes to the group"""
        wish_payload = WishModelUpdate.model_validate(payload.post_values)

        # Update the wish
        do_update_wish(self.current_user, payload.object_id, wish_payload)

        action = "update_wish"
        if wish_payload.dict()["assigned_user"] is not None:
            action = "change_wish_assigned_user"

        # Send the updated wishes to the groups
        self._send_update_wishes(action=action)

    def create_wish(self, payload: WebhookPayloadModel):
        """Create a wish and send the updated wishes to the group"""
        wish_payload = WishModel.model_validate(payload.post_values)

        # Add the wishlist user
        wish_data = wish_payload.dict()
        wish_data.update({"wishlist_user": self.current_user})

        Wish.objects.create(**wish_data)

        # Send the updated wishes to the groups
        self._send_update_wishes(action="create_wish")

    def delete_wish(self, payload: WebhookPayloadModel):
        """Delete a wish and send the updated wishes to the group"""
        instance = get_object_or_404(Wish, pk=payload.object_id)

        can_be_deleted, error_message = instance.can_be_deleted(self.current_user.id)
        if not can_be_deleted:
            raise SimpleWishlistValidationError(model="Wish", field=None, message=error_message)

        instance.mark_deleted()

        # Send the updated wishes to the groups
        self._send_update_wishes(action="delete_wish")

    def _send_update_wishes(self, action: str = "update_wishes"):
        """Send the updated wishes to the group"""
        users_wishes = get_all_users_wishes(self.wishlist, as_dict=True)

        # Needed to serialize the uuid
        data = json.dumps(users_wishes, cls=DjangoJSONEncoder)

        self.send_group_message("update_wishes", action, json.loads(data))

    # RESPONSES
    def send_group_message(self, type: str, action: str, data: dict | list | str):
        """
        Send a message to the group with the given type and data
        The type is the name of the method to call in the consumer
        """
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name,
            {"type": type, "data": data, "userToken": self.current_user.name, "action": action},
        )

    def send_individual_message(self, event: dict):
        # Use to send a message to the individual user and not the group
        self.send_json(content=json.dumps(event, cls=DjangoJSONEncoder))

    def update_wishes(self, event: dict):
        self.send_individual_message(event)

    def error_message(self, event: dict):
        self.send_individual_message(event)

    def new_group_member_connection(self, event: dict):
        self.send_individual_message(event)
