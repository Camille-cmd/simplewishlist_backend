from typing import List

from asgiref.sync import async_to_sync
from channels.exceptions import StopConsumer
from channels.generic.websocket import JsonWebsocketConsumer
from django.shortcuts import get_object_or_404
from pydantic import TypeAdapter

from api.exceptions import SimpleWishlistValidationError
from api.pydantic_models import (
    WishModelUpdate,
    WebhookPayloadModel,
    WishModel,
    WishModelUpdateAssignUser,
    WishListUserModel,
)
from api.utils import get_all_users_wishes, do_update_wish
from core.models import WishListUser, Wish


class WishlistConsumer(JsonWebsocketConsumer):
    current_user = None
    wishlist = None

    def connect(self):
        """On connect, we get the user from the URL and join the group with the wishlist id"""
        # If the user is not found, we close the connection
        try:
            self.current_user = WishListUser.objects.get(pk=self.scope["url_route"]["kwargs"]["wishlist_user"])

            self.wishlist = self.current_user.wishlist

            self.room_group_name = f"wishlist_{self.wishlist.id}"

            # Join room group
            async_to_sync(self.channel_layer.group_add)(self.room_group_name, self.channel_name)

            self.accept("authorization")

        except WishListUser.DoesNotExist:
            self.close(reason="User not found")

    def disconnect(self, close_code):
        """On disconnect, we leave the group"""
        raise StopConsumer()

    def receive_json(self, content: dict, **kwargs):
        """Receive a message from the group and process it"""
        try:
            # Validate the payload
            payload = WebhookPayloadModel.model_validate(content)

            match payload.type:
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

    def update_wish(self, payload: WebhookPayloadModel):
        """Assign a wish to a user and send the updated wishes to the group"""
        # We need to check if the only field is the assigned_user, meaning that we are changing the assigned user
        changing_assigned_user = list(payload.post_values.keys()) == ["assignedUser"]
        if changing_assigned_user:
            # If the only field is the assigned_user, we can use the WishModelUpdateAssignUser
            wish_payload = WishModelUpdateAssignUser.model_validate(payload.post_values)
        else:
            wish_payload = WishModelUpdate.model_validate(payload.post_values)

        # Update the wish => if the assigned_user is changing, we need to keep the None values
        do_update_wish(self.current_user, payload.object_id, wish_payload, exclude_unset=not changing_assigned_user)

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
        users_wishes = get_all_users_wishes(self.wishlist, current_user=self.current_user)

        # Convert the list of Pydantic models to a list of dictionaries
        users_wishes_adapter = TypeAdapter(List[WishListUserModel])  # "Lambda" pydantic model
        users_wishes = users_wishes_adapter.dump_python(users_wishes, by_alias=True, mode="json")

        self.send_group_message("update_wishes", action, users_wishes)

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

    def send_individual_message(self, content: dict):
        # Use to send a message to the individual user and not the group
        self.send_json(content=content)

    def update_wishes(self, content: dict):
        self.send_individual_message(content)

    def error_message(self, content: dict):
        self.send_individual_message(content)

    def new_group_member_connection(self, content: dict):
        self.send_individual_message(content)
