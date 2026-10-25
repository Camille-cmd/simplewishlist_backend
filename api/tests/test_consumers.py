import random
from uuid import UUID

from asgiref.sync import sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings

from api.routing import websocket_urlpatterns
from api.tests.factories import WishListFactory, WishListUserFactory, WishFactory
from core.models import Wish


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.dummy.DummyCache",
        }
    }
)
class WishlistConsumerTest(TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.application = URLRouter(websocket_urlpatterns)

        self.wishlist = WishListFactory(wishlist_name="Test Wishlist")
        self.user = WishListUserFactory(name="Bob", wishlist=self.wishlist)
        self.second_user = WishListUserFactory(name="Alice", wishlist=self.wishlist)
        self.third_user = WishListUserFactory(name="Charlie", wishlist=self.wishlist)

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
                        "assignedUsers": [],
                        "suggestedBy": None,
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
                        "assignedUsers": [],
                        "suggestedBy": None,
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
                        "assignedUsers": ["Bob"],
                        "suggestedBy": None,
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
            {
                "type": "error_message",
                "data": "Modifying assigned user unauthorized",
                "code": "wish_assignment_unauthorized",
            },
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

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user)
        await sync_to_async(wish.assigned_users.add)(self.second_user)
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
                    "assignedUsers": ["Alice"],
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
                "data": {"user": "Bob", "wishId": str(wish.id), "assignedUsers": []},
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

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user, deleted=True)
        await sync_to_async(wish.assigned_users.add)(self.second_user)
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
                "data": {"user": "Bob", "wishId": str(wish.id), "assignedUsers": []},
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
                "code": "wish_delete_unauthorized",
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

    async def test_create_suggested_wish(self):
        """Test that the WishlistConsumer creates a suggested wish correctly."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # User (Bob) suggests a wish for second_user (Alice)
        post_values = {
            "name": "Suggested wish",
            "price": "50.0",
            "url": "http://example.com/suggested",
            "suggestedForUserId": str(self.second_user.id),
        }
        data = {
            "type": "create_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": None,
        }

        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        # Verify the wish was created
        wish_created = await sync_to_async(Wish.objects.get)(name="Suggested wish")
        self.assertIsNotNone(wish_created)

        # Access related fields with sync_to_async
        wishlist_user_id = await sync_to_async(lambda: wish_created.wishlist_user.id)()
        suggested_by_id = await sync_to_async(lambda: wish_created.suggested_by.id)()

        self.assertEqual(wishlist_user_id, self.second_user.id)
        self.assertEqual(suggested_by_id, self.user.id)

        # Verify the response
        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {
                    "user": "Alice",
                    "wish": {
                        "name": "Suggested wish",
                        "deleted": False,
                        "price": "50.0",
                        "url": "http://example.com/suggested",
                        "description": None,
                        "id": str(wish_created.id),
                        "assignedUsers": [],
                        "suggestedBy": "Bob",
                    },
                },
                "userToken": "Bob",
                "action": "create_wish",
            },
        )

        await communicator.disconnect()

    async def test_suggester_can_edit_suggested_wish(self):
        """Test that the suggester can edit their suggested wish."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Create a suggested wish (Bob suggests for Alice)
        wish = await sync_to_async(WishFactory)(
            wishlist_user=self.second_user, suggested_by=self.user, name="Original name"
        )

        # Bob (suggester) tries to edit the wish
        post_values = {
            "name": "Updated name",
            "price": "100.0",
        }
        data = {
            "type": "update_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": str(wish.id),
        }

        await communicator.send_json_to(data)
        await communicator.receive_json_from()

        # Verify the wish was updated
        updated_wish = await sync_to_async(Wish.objects.get)(id=wish.id)
        self.assertEqual(updated_wish.name, "Updated name")
        self.assertEqual(updated_wish.price, "100.0")

        await communicator.disconnect()

    async def test_wish_owner_cannot_edit_suggested_wish(self):
        """Test that the wish owner cannot edit a suggested wish."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.second_user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Create a suggested wish (Bob suggests for Alice)
        wish = await sync_to_async(WishFactory)(
            wishlist_user=self.second_user, suggested_by=self.user, name="Original name"
        )

        # Alice (wish owner) tries to edit the wish
        post_values = {
            "name": "Updated name",
        }
        data = {
            "type": "update_wish",
            "currentUser": str(self.second_user.id),
            "post_values": post_values,
            "objectId": str(wish.id),
        }

        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        # Verify the error message
        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "Only the suggester can edit this suggested wish.",
                "code": "wish_suggested_edit_unauthorized",
            },
        )

        # Verify the wish was not updated
        wish_after = await sync_to_async(Wish.objects.get)(id=wish.id)
        self.assertEqual(wish_after.name, "Original name")

        await communicator.disconnect()

    async def test_suggester_can_delete_suggested_wish(self):
        """Test that the suggester can delete their suggested wish."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Create a suggested wish (Bob suggests for Alice)
        wish = await sync_to_async(WishFactory)(wishlist_user=self.second_user, suggested_by=self.user)

        # Bob (suggester) tries to delete the wish
        await communicator.send_json_to(
            {
                "type": "delete_wish",
                "currentUser": str(self.user.id),
                "objectId": str(wish.id),
            }
        )
        await communicator.receive_json_from()

        # Verify the wish was deleted
        with self.assertRaises(Wish.DoesNotExist):
            await sync_to_async(Wish.objects.get)(id=wish.id)

        await communicator.disconnect()

    async def test_wish_owner_cannot_delete_suggested_wish(self):
        """Test that the wish owner cannot delete a suggested wish."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.second_user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Create a suggested wish (Bob suggests for Alice)
        wish = await sync_to_async(WishFactory)(wishlist_user=self.second_user, suggested_by=self.user)

        # Alice (wish owner) tries to delete the wish
        await communicator.send_json_to(
            {
                "type": "delete_wish",
                "currentUser": str(self.second_user.id),
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        # Verify the error message
        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "Only the suggester can delete this suggested wish.",
                "code": "wish_suggested_delete_unauthorized",
            },
        )

        # Verify the wish still exists
        wish_after = await sync_to_async(Wish.objects.get)(id=wish.id)
        self.assertIsNotNone(wish_after)

        await communicator.disconnect()

    async def test_suggested_wish_can_be_assigned(self):
        """Test that a suggested wish can be assigned/taken by other users."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Create a suggested wish (Bob suggests for Alice)
        wish = await sync_to_async(WishFactory)(wishlist_user=self.second_user, suggested_by=self.user)

        # Third user would take this wish, but we'll use Bob for simplicity
        # Bob (not the owner) takes the wish
        post_values = {"assignedUser": str(self.user.id)}
        data = {
            "type": "update_wish",
            "currentUser": str(self.user.id),
            "post_values": post_values,
            "objectId": str(wish.id),
        }

        await communicator.send_json_to(data)
        response = await communicator.receive_json_from()

        # Verify the wish was assigned
        updated_wish = await sync_to_async(Wish.objects.get)(id=wish.id)
        assigned_user_ids = await sync_to_async(lambda: [u.id for u in updated_wish.assigned_users.all()])()
        self.assertEqual(assigned_user_ids, [self.user.id])

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
                        "assignedUsers": ["Bob"],
                        "suggestedBy": "Bob",
                    },
                },
                "userToken": "Bob",
                "action": "change_wish_assigned_user",
            },
        )

        await communicator.disconnect()

    async def test_two_users_take_same_wish(self):
        """Test that two different users can take the same wish and release it independently."""
        communicator_bob = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator_bob.connect()
        # First message is the connection message
        await communicator_bob.receive_json_from()

        # Charlie owns the wish so that both Bob and Alice can take it (the owner can never take it)
        wish = await sync_to_async(WishFactory)(wishlist_user=self.third_user)

        # Bob takes the wish
        await communicator_bob.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.user.id),
                "post_values": {"assignedUser": str(self.user.id)},
                "objectId": str(wish.id),
            }
        )
        response = await communicator_bob.receive_json_from()
        self.assertEqual(
            response,
            {
                "type": "updated_wish",
                "data": {
                    "user": "Charlie",
                    "wish": {
                        "name": wish.name,
                        "deleted": False,
                        "price": None,
                        "url": None,
                        "description": None,
                        "id": str(wish.id),
                        "assignedUsers": ["Bob"],
                        "suggestedBy": None,
                    },
                },
                "userToken": "Bob",
                "action": "change_wish_assigned_user",
            },
        )

        # Alice connects
        communicator_alice = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.second_user.id}/")
        await communicator_alice.connect()
        # Both members receive the new member connection message
        await communicator_bob.receive_json_from()
        await communicator_alice.receive_json_from()

        # Alice takes the same wish
        await communicator_alice.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.second_user.id),
                "post_values": {"assignedUser": str(self.second_user.id)},
                "objectId": str(wish.id),
            }
        )
        # Both members receive the update
        expected_response = {
            "type": "updated_wish",
            "data": {
                "user": "Charlie",
                "wish": {
                    "name": wish.name,
                    "deleted": False,
                    "price": None,
                    "url": None,
                    "description": None,
                    "id": str(wish.id),
                    "assignedUsers": ["Bob", "Alice"],
                    "suggestedBy": None,
                },
            },
            "userToken": "Alice",
            "action": "change_wish_assigned_user",
        }
        self.assertEqual(await communicator_bob.receive_json_from(), expected_response)
        self.assertEqual(await communicator_alice.receive_json_from(), expected_response)

        # Alice releases the wish, Bob keeps it
        await communicator_alice.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.second_user.id),
                "post_values": {"assignedUser": None},
                "objectId": str(wish.id),
            }
        )
        expected_response = {
            "type": "updated_wish",
            "data": {
                "user": "Charlie",
                "wish": {
                    "name": wish.name,
                    "deleted": False,
                    "price": None,
                    "url": None,
                    "description": None,
                    "id": str(wish.id),
                    "assignedUsers": ["Bob"],
                    "suggestedBy": None,
                },
            },
            "userToken": "Alice",
            "action": "update_wish",
        }
        self.assertEqual(await communicator_bob.receive_json_from(), expected_response)
        self.assertEqual(await communicator_alice.receive_json_from(), expected_response)

        await communicator_bob.disconnect()
        await communicator_alice.disconnect()

    async def test_take_soft_deleted_wish_error(self):
        """Test that a user cannot take a wish that has been marked as deleted."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.second_user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Bob's wish, taken by Charlie, then soft-deleted by Bob
        wish = await sync_to_async(WishFactory)(wishlist_user=self.user, deleted=True)
        await sync_to_async(wish.assigned_users.add)(self.third_user)

        # Alice tries to take the soft-deleted wish
        await communicator.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.second_user.id),
                "post_values": {"assignedUser": str(self.second_user.id)},
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "This wish has been deleted.",
                "code": "wish_deleted",
            },
        )

        await communicator.disconnect()

    async def test_double_take_error_code(self):
        """Test that taking a wish twice returns the wish_already_taken error code."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.second_user)

        # Bob takes the wish
        await communicator.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.user.id),
                "post_values": {"assignedUser": str(self.user.id)},
                "objectId": str(wish.id),
            }
        )
        await communicator.receive_json_from()

        # Bob tries to take it again
        await communicator.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.user.id),
                "post_values": {"assignedUser": str(self.user.id)},
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "You have already taken this wish.",
                "code": "wish_already_taken",
            },
        )

        await communicator.disconnect()

    async def test_owner_take_own_wish_error_code(self):
        """Test that the owner of a wish cannot take their own wish."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        wish = await sync_to_async(WishFactory)(wishlist_user=self.user)

        await communicator.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.user.id),
                "post_values": {"assignedUser": str(self.user.id)},
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "Modifying assigned user unauthorized",
                "code": "wish_assignment_unauthorized",
            },
        )

        await communicator.disconnect()

    async def test_unauthorized_edit_error_code(self):
        """Test that a non-owner editing a regular wish returns the wish_edit_unauthorized error code."""
        communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{self.second_user.id}/")
        await communicator.connect()
        # First message is the connection message
        await communicator.receive_json_from()

        # Bob's wish, Alice tries to edit it
        wish = await sync_to_async(WishFactory)(wishlist_user=self.user)

        await communicator.send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.second_user.id),
                "post_values": {"name": "Hacked name"},
                "objectId": str(wish.id),
            }
        )
        response = await communicator.receive_json_from()

        self.assertEqual(
            response,
            {
                "type": "error_message",
                "data": "Only the owner of the wish can change the wish data.",
                "code": "wish_edit_unauthorized",
            },
        )

        await communicator.disconnect()

    async def test_delete_flow_with_multiple_takers(self):
        """
        Test the full delete flow when several users have taken the same wish:
        the owner deletes it (soft delete), each taker releases it, and the wish
        is permanently deleted once the last taker releases it.
        """
        communicators = {}
        for name, user in [("charlie", self.third_user), ("bob", self.user), ("alice", self.second_user)]:
            communicator = WebsocketCommunicator(self.application, f"/ws/wishlist/{user.id}/")
            await communicator.connect()
            # All members of the group receive the new member connection message
            for existing_communicator in communicators.values():
                await existing_communicator.receive_json_from()
            await communicator.receive_json_from()
            communicators[name] = communicator

        # Charlie creates a wish, taken by both Bob and Alice
        wish = await sync_to_async(WishFactory)(wishlist_user=self.third_user)
        await sync_to_async(wish.assigned_users.add)(self.user)
        await sync_to_async(wish.assigned_users.add)(self.second_user)

        # Charlie (owner) deletes the wish => soft delete since it has takers
        await communicators["charlie"].send_json_to(
            {
                "type": "delete_wish",
                "currentUser": str(self.third_user.id),
                "objectId": str(wish.id),
            }
        )
        expected_response = {
            "type": "updated_wish",
            "data": {
                "user": "Charlie",
                "wishId": str(wish.id),
                "assignedUsers": ["Bob", "Alice"],
            },
            "userToken": "Charlie",
            "action": "delete_wish",
        }
        for communicator in communicators.values():
            self.assertEqual(await communicator.receive_json_from(timeout=5), expected_response)

        wish = await sync_to_async(Wish.objects.get)(id=wish.id)
        self.assertTrue(wish.deleted)

        # Bob releases the wish => still soft-deleted (Alice still has it)
        await communicators["bob"].send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.user.id),
                "post_values": {"assignedUser": None},
                "objectId": str(wish.id),
            }
        )
        expected_response = {
            "type": "updated_wish",
            "data": {
                "user": "Charlie",
                "wish": {
                    "name": wish.name,
                    "deleted": True,
                    "price": None,
                    "url": None,
                    "description": None,
                    "id": str(wish.id),
                    "assignedUsers": ["Alice"],
                    "suggestedBy": None,
                },
            },
            "userToken": "Bob",
            "action": "update_wish",
        }
        # Receive from the actor (Bob) first so that any individual error_message
        # surfaces as an assertion failure instead of an opaque timeout on the others
        self.assertEqual(await communicators["bob"].receive_json_from(timeout=5), expected_response)
        for name in ("charlie", "alice"):
            self.assertEqual(await communicators[name].receive_json_from(timeout=5), expected_response)

        wish = await sync_to_async(Wish.objects.get)(id=wish.id)
        self.assertTrue(wish.deleted)

        # Alice (last taker) releases the wish => permanent deletion
        await communicators["alice"].send_json_to(
            {
                "type": "update_wish",
                "currentUser": str(self.second_user.id),
                "post_values": {"assignedUser": None},
                "objectId": str(wish.id),
            }
        )
        expected_response = {
            "type": "updated_wish",
            "data": {
                "user": "Charlie",
                "wishId": str(wish.id),
                "assignedUsers": [],
            },
            "userToken": "Alice",
            "action": "delete_wish",
        }
        for communicator in communicators.values():
            self.assertEqual(await communicator.receive_json_from(timeout=5), expected_response)

        with self.assertRaises(Wish.DoesNotExist):
            await sync_to_async(Wish.objects.get)(id=wish.id)

        for communicator in communicators.values():
            await communicator.disconnect()
