import random
from uuid import UUID

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase

from api.routing import websocket_urlpatterns
from api.tests.factories import WishListFactory, WishListUserFactory, WishFactory
from core.models import Wish


class WishlistConsumerTest(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.application = URLRouter(websocket_urlpatterns)

        self.wishlist = WishListFactory(wishlist_name="Test Wishlist")
        self.user = WishListUserFactory(name="Bob", wishlist=self.wishlist)
        self.second_user = WishListUserFactory(name="Alice", wishlist=self.wishlist)

    async def test_connects(self):
        """Test that the WishlistConsumer successfully connects."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")

        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        await communicator.disconnect()

    async def test_rejects_unauthorized_user(self):
        """Test that the WishlistConsumer rejects an unauthorized user."""
        # Connect with a non-existing user
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{str(fake_uuid)}/")
        await communicator.send_input({"type": "websocket.connect"})
        response = await communicator.receive_output(timeout=1)
        self.assertEqual(response, {"reason": "User not found", "type": "websocket.close"})

    async def test_create_wish_correctly(self):
        """
        Test that the WishlistConsumer handles a create wish message correctly.
        get_all_users_wishes is mocked because it is already tested in the test_get_wishlist test.
        """
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        post_values = {
            "name": "Test wish",
            "price": "10.0",
            "url": "http://example.com/",
        }
        data = {
            "type": "create_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": None,
        }

        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        wish_created = await sync_to_async(Wish.objects.get)(**post_values)
        self.assertIsNotNone(wish_created)
        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {
                    "user": "Bob",
                    "wish": {
                        "name": "Test wish",
                        "deleted": False,
                        "price": "10.0",
                        "url": "http://example.com/",
                        "description": None,
                        "id": str(wish_created.id),
                        "assignedUser": None,
                    },
                },
                "userToken": "Bob",
                "action": "create_wish",
            },
        )

        await communicator.disconnect()

    async def test_create_wish_invalid_data(self):
        """Test that the WishlistConsumer sends an error message when receiving invalid data."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Invalid data
        await communicator.send_json_to(
            {
                "type": "create_wish",
                "currentUser": str(self.user.id),
                "post_values": {
                    "name": "Test wish",
                    "price": "price is limited to 10 char",
                    "url": "http://example.com/",
                },
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "value too long for type character varying(15)\n",
            },
        )

        await communicator.disconnect()

    async def test_update_wish_correctly(self):
        """Test that the WishlistConsumer updates a wish correctly."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user)
        post_values = {
            "name": "Test wish",
            "price": "10.0",
            "url": "http://example.com/",
        }
        data = {
            "type": "update_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": str(wish.id),
        }

        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        updated_wish = await sync_to_async(Wish.objects.get)(id=wish.id)
        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {
                    "user": "Bob",
                    "wish": {
                        "name": "Test wish",
                        "deleted": False,
                        "price": "10.0",
                        "url": "http://example.com/",
                        "description": None,
                        "id": str(updated_wish.id),
                        "assignedUser": None,
                    },
                },
                "userToken": "Bob",
                "action": "update_wish",
            },
        )

        self.assertEqual(updated_wish.name, post_values["name"])
        self.assertEqual(updated_wish.price, post_values["price"])
        self.assertEqual(updated_wish.url, post_values["url"])

        await communicator.disconnect()

    async def test_update_wish_assign_user(self):
        """Test that the WishlistConsumer updates a wish's assigned user correctly."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # User takes second user's wish
        wish = await sync_to_async(WishFactory)(wishlist_user=self.second_user)
        post_values = {"assigned_user": str(self.user.id)}
        data = {
            "type": "update_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": str(wish.id),
        }

        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {
                    "user": "Alice",
                    "wish": {
                        "name": wish.name,
                        "deleted": False,
                        "price": None,
                        "url": None,
                        "description": None,
                        "id": str(wish.id),
                        "assignedUser": "Bob",
                    },
                },
                "userToken": "Bob",
                "action": "change_wish_assigned_user",
            },
        )

        await communicator.disconnect()

    async def test_update_wish_change_assign_user_unauthorised(self):
        """
        Test that the WishlistConsumer returns error message when trying to change a user unauthorised.
        """
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user)
        post_values = {"assigned_user": str(self.second_user.id)}
        data = {
            "type": "update_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": str(wish.id),
        }

        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        # The assigned user is the owner of the wish, so the user can not change it
        self.assertEqual(
            response,
            {"type": "error_message", "data": "Modifying assigned user unauthorized"},
        )

        await communicator.disconnect()

    async def test_delete_wish_no_matching_wish(self):
        """Test that the WishlistConsumer sends an error message when trying to delete a non-existing wish."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        connected, _ = await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()
        self.assertTrue(connected)

        # Non-existing wish id
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        await communicator.send_json_to(
            {
                "type": "delete_wish",
                "currentUser": str(self.user.id),
                "objectId": str(fake_uuid),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {"type": "error_message", "data": "No Wish matches the given query."},
        )

        await communicator.disconnect()

    async def test_delete_wish_mark_deleted_already_assigned(self):
        """Test that the WishlistConsumer only mark the wish as deleted if it has an assigned user."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user, assigned_user=self.second_user)
        await communicator.send_json_to(
            {
                "type": "delete_wish",
                "currentUser": str(self.user.id),
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {
                    "user": "Bob",
                    "wishId": str(wish.id),
                    "assignedUser": "Alice",
                },
                "userToken": "Bob",
                "action": "delete_wish",
            },
        )

        wish = await sync_to_async(Wish.objects.get)(id=wish.id)
        self.assertTrue(wish.deleted)

        await communicator.disconnect()

    async def test_delete_wish_mark_deleted_but_not_assigned(self):
        """Test that the WishlistConsumer completely deletes the wish if it has no assigned user."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user)
        await communicator.send_json_to(
            {
                "type": "delete_wish",
                "currentUser": str(self.user.id),
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {"user": "Bob", "wishId": str(wish.id), "assignedUser": None},
                "userToken": "Bob",
                "action": "delete_wish",
            },
        )

        with self.assertRaises(Wish.DoesNotExist):
            await sync_to_async(Wish.objects.get)(id=wish.id)

        await communicator.disconnect()

    async def test_delete_wish_mark_deleted_is_unassigned(self):
        """Test that when a user unassign a wish, and it was marked as deleted, it is completely deleted."""

        # Second user took the wish and now unassigns himself
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.second_user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user, assigned_user=self.second_user, deleted=True)
        post_values = {"assignedUser": None}
        data = {
            "type": "update_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": str(wish.id),
        }
        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {"user": "Bob", "wishId": str(wish.id), "assignedUser": None},
                "userToken": "Alice",
                "action": "delete_wish",
            },
        )

        with self.assertRaises(Wish.DoesNotExist):
            await sync_to_async(Wish.objects.get)(id=wish.id)

        await communicator.disconnect()

    async def test_delete_wish_can_not_be_deleted(self):
        """
        Test that the WishlistConsumer sends an error message when trying to delete a wish that can not be deleted.
        """
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.second_user)
        # User tries to delete the wish, but it can only be deleted by second user
        await communicator.send_json_to(
            {
                "type": "delete_wish",
                "currentUser": str(self.user.id),
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "Only the owner of the wish can delete it.",
            },
        )

        await communicator.disconnect()

    async def test_invalid_action(self):
        """Test that the WishlistConsumer sends an error message when receiving an invalid action."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        await communicator.send_json_to({"type": "invalid_action", "currentUser": str(self.user.id)})
        response = await communicator.receive_json_from()

        self.assertEqual(response, {"type": "error_message", "data": "Invalid action"})

        await communicator.disconnect()
