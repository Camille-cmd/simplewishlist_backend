from asgiref.sync import async_to_sync
from channels.exceptions import StopConsumer
from channels.generic.websocket import JsonWebsocketConsumer
from django.shortcuts import get_object_or_404

from api.RedisForWishList import RedisForWishList
from api.exceptions import SimpleWishlistValidationError
from api.pydantic_models import (
    WishModelUpdate,
    WebhookPayloadModel,
    WishModel,
    WishModelUpdateAssignUser,
    WishListWishModel,
    UserWishDataModel,
    UserDeletedWishDataModel,
)
from api.utils import do_update_wish
from core.models import WishListUser, Wish


class WishlistConsumer(JsonWebsocketConsumer):
    current_user = None
    wishlist = None
    room_group_name = None
    redis = RedisForWishList()

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

            # Alert the group that a new user has connected
            room_connected_users = self.redis.get_currently_connected_users(self.room_group_name, self.current_user)
            self.send_group_message(
                "new_group_member_connection",
                "new_group_member_connection",
                room_connected_users,
            )

        except WishListUser.DoesNotExist:
            self.close(reason="User not found")

    def disconnect(self, close_code):
        """On disconnect, we leave the group"""
        # Handle user disconnection follow up
        room_connected_users = self.redis.remove_user_from_connected_users(self.room_group_name, self.current_user)

        # Send the updated list of connected users to the group
        self.send_group_message(
            "group_member_disconnected",
            "group_member_disconnected",
            room_connected_users,
        )

        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(self.room_group_name, self.channel_name)
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
        updated_wish = do_update_wish(
            self.current_user, payload.object_id, wish_payload, exclude_unset=not changing_assigned_user
        )

        # When we un-assign a deleted wish, this is a permanent deletion
        # and the wish was completely deleted during do_update_wish
        if changing_assigned_user and updated_wish.deleted:
            # Prepare data in case the wish was deleted
            deleted_wish_data = {
                "wish_id": payload.object_id,
                "wish_user_name": updated_wish.wishlist_user.name,
                "assigned_user": None,
            }
            # Try to update, if the object no longer exists, it will return None
            try:
                updated_wish = updated_wish.refresh_from_db()
            except Wish.DoesNotExist:
                self._send_updated_wish(
                    wish=None,  # handle delete cases with just the wish_id (it will be displayed as deleted)
                    action="delete_wish",
                    deleted_wish_data=deleted_wish_data,
                )
                return

        action = "update_wish"
        if wish_payload.dict()["assigned_user"] is not None:
            action = "change_wish_assigned_user"

        # Send the updated wishes to the groups
        self._send_updated_wish(wish=updated_wish, action=action)

    def create_wish(self, payload: WebhookPayloadModel):
        """Create a wish and send the updated wishes to the group"""
        wish_payload = WishModel.model_validate(payload.post_values)

        # Add the wishlist user
        wish_data = wish_payload.dict()
        wish_data.update({"wishlist_user": self.current_user})

        created_wish = Wish.objects.create(**wish_data)

        # Send the updated wishes to the groups
        self._send_updated_wish(wish=created_wish, action="create_wish")

    def delete_wish(self, payload: WebhookPayloadModel):
        """Delete a wish and send the updated wishes to the group"""
        instance = get_object_or_404(Wish, pk=payload.object_id)
        wish_user_name = instance.wishlist_user.name
        assigned_user = instance.assigned_user.name if instance.assigned_user else None
        deleted_wish_data = {"wish_id": instance.id, "wish_user_name": wish_user_name, "assigned_user": assigned_user}
        can_be_deleted, error_message = instance.can_be_deleted(self.current_user.id)
        if not can_be_deleted:
            raise SimpleWishlistValidationError(model="Wish", field=None, message=error_message)

        instance.mark_deleted()

        # Send the updated wishes to the groups
        self._send_updated_wish(
            wish=None,  # handle delete cases with just the wish_id (it will be displayed as deleted)
            action="delete_wish",
            deleted_wish_data=deleted_wish_data,
        )

    def _send_updated_wish(self, wish: Wish | None, action: str = "update_wish", deleted_wish_data: dict = None):
        """Send the updated wishes to the group"""
        if action == "delete_wish":
            user_wish_data = UserDeletedWishDataModel(
                user=deleted_wish_data["wish_user_name"],
                wish_id=deleted_wish_data["wish_id"],
                assigned_user=deleted_wish_data["assigned_user"],
            )
        else:
            wish_data = WishListWishModel(
                name=wish.name,
                price=wish.price or None,
                description=wish.description or None,
                url=wish.url or None,
                id=wish.id,
                assigned_user=wish.assigned_user.name if wish.assigned_user else None,
                deleted=wish.deleted,
            )
            user_wish_data = UserWishDataModel(user=wish.wishlist_user.name, wish=wish_data)

        user_wish_data_dumped = user_wish_data.model_dump(by_alias=True, mode="json")

        self.send_group_message("updated_wish", action, user_wish_data_dumped)

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

    def updated_wish(self, content: dict):
        self.send_individual_message(content)

    def error_message(self, content: dict):
        self.send_individual_message(content)

    def new_group_member_connection(self, content: dict):
        self.send_individual_message(content)

    def group_member_disconnected(self, content: dict):
        self.send_individual_message(content)
