from django.test import TestCase

from api.tests.factories import WishListFactory, WishListUserFactory, WishFactory
from api.utils import get_all_users_wishes


class TestGetAllUsersWishes(TestCase):
    """Test the get_all_users_wishes utility function"""

    def setUp(self):
        self.wishlist = WishListFactory(wishlist_name="Test Wishlist")
        self.user = WishListUserFactory(name="Bob", wishlist=self.wishlist)
        self.second_user = WishListUserFactory(name="Alice", wishlist=self.wishlist)
        self.third_user = WishListUserFactory(name="Charlie", wishlist=self.wishlist)

    def test_suggested_wishes_hidden_from_owner(self):
        """Test that suggested wishes are hidden from the wish owner but visible to others."""
        # Bob suggests a wish for Alice
        WishFactory(
            name="Suggested wish for Alice",
            wishlist_user=self.second_user,
            suggested_by=self.user,
        )

        # Alice creates a regular wish
        WishFactory(
            name="Alice's regular wish",
            wishlist_user=self.second_user,
        )

        # Get wishes from Alice's perspective (she is current_user)
        users_wishes = get_all_users_wishes(self.wishlist, self.second_user)

        # Find Alice's wishes in the result
        alice_wishes = None
        for user_wish in users_wishes:
            if user_wish.user == "Alice":
                alice_wishes = user_wish.wishes
                break

        # Alice should only see her regular wish, not the suggested one
        self.assertIsNotNone(alice_wishes)
        self.assertEqual(len(alice_wishes), 1)
        self.assertEqual(alice_wishes[0].name, "Alice's regular wish")
        self.assertIsNone(alice_wishes[0].suggested_by)

        # Get wishes from Bob's perspective (he is current_user)
        users_wishes_bob = get_all_users_wishes(self.wishlist, self.user)

        # Find Alice's wishes in the result
        alice_wishes_bob = None
        for user_wish in users_wishes_bob:
            if user_wish.user == "Alice":
                alice_wishes_bob = user_wish.wishes
                break

        # Bob should see both Alice's regular wish and the suggested wish
        self.assertIsNotNone(alice_wishes_bob)
        self.assertEqual(len(alice_wishes_bob), 2)

        # Find the suggested wish
        suggested_wish_found = None
        regular_wish_found = None
        for wish in alice_wishes_bob:
            if wish.suggested_by:
                suggested_wish_found = wish
            else:
                regular_wish_found = wish

        self.assertIsNotNone(suggested_wish_found)
        self.assertEqual(suggested_wish_found.name, "Suggested wish for Alice")
        self.assertEqual(suggested_wish_found.suggested_by, "Bob")

        self.assertIsNotNone(regular_wish_found)
        self.assertEqual(regular_wish_found.name, "Alice's regular wish")

    def test_regular_wishes_visible_to_owner(self):
        """Test that regular wishes are visible to their owner."""
        # Bob creates a regular wish
        WishFactory(
            name="Bob's wish",
            wishlist_user=self.user,
        )

        # Get wishes from Bob's perspective
        users_wishes = get_all_users_wishes(self.wishlist, self.user)

        # Find Bob's wishes
        bob_wishes = None
        for user_wish in users_wishes:
            if user_wish.user == "Bob":
                bob_wishes = user_wish.wishes
                break

        # Bob should see his regular wish
        self.assertIsNotNone(bob_wishes)
        self.assertEqual(len(bob_wishes), 1)
        self.assertEqual(bob_wishes[0].name, "Bob's wish")
        self.assertIsNone(bob_wishes[0].suggested_by)

    def test_multiple_suggested_wishes_filtering(self):
        """Test that multiple suggested wishes are all hidden from the owner."""
        # Bob suggests two wishes for Alice
        WishFactory(
            name="Suggested wish 1",
            wishlist_user=self.second_user,
            suggested_by=self.user,
        )
        WishFactory(
            name="Suggested wish 2",
            wishlist_user=self.second_user,
            suggested_by=self.third_user,
        )

        # Alice creates one regular wish
        WishFactory(
            name="Regular wish",
            wishlist_user=self.second_user,
        )

        # Get wishes from Alice's perspective
        users_wishes = get_all_users_wishes(self.wishlist, self.second_user)

        # Find Alice's wishes
        alice_wishes = None
        for user_wish in users_wishes:
            if user_wish.user == "Alice":
                alice_wishes = user_wish.wishes
                break

        # Alice should only see her regular wish
        self.assertIsNotNone(alice_wishes)
        self.assertEqual(len(alice_wishes), 1)
        self.assertEqual(alice_wishes[0].name, "Regular wish")

        # Get wishes from Charlie's perspective
        users_wishes_charlie = get_all_users_wishes(self.wishlist, self.third_user)

        # Find Alice's wishes
        alice_wishes_charlie = None
        for user_wish in users_wishes_charlie:
            if user_wish.user == "Alice":
                alice_wishes_charlie = user_wish.wishes
                break

        # Charlie should see all three wishes
        self.assertIsNotNone(alice_wishes_charlie)
        self.assertEqual(len(alice_wishes_charlie), 3)

    def test_suggested_by_field_included_in_response(self):
        """Test that the suggested_by field is included in the response."""
        # Bob suggests a wish for Alice
        WishFactory(
            name="Suggested wish",
            wishlist_user=self.second_user,
            suggested_by=self.user,
        )

        # Get wishes from Bob's perspective
        users_wishes = get_all_users_wishes(self.wishlist, self.user)

        # Find Alice's wishes
        alice_wishes = None
        for user_wish in users_wishes:
            if user_wish.user == "Alice":
                alice_wishes = user_wish.wishes
                break

        # The suggested wish should have suggested_by field
        self.assertIsNotNone(alice_wishes)
        self.assertEqual(len(alice_wishes), 1)
        self.assertEqual(alice_wishes[0].suggested_by, "Bob")
