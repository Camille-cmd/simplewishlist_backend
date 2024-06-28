import random
from unittest.mock import patch
from uuid import UUID

from api.exceptions import SimpleWishlistValidationError
from api.pydantic_models import WishModelUpdate
from api.tests.factories import WishFactory, WishListUserFactory
from api.tests.utils import SimpleWishlistBaseTestCase
from core.models import Wish, WishListUser


class TestWishListUser(SimpleWishlistBaseTestCase):
    def setUp(self):
        super().setUp()
        # Create Wishes for the user
        self.unassigned_wish = WishFactory.create(
            name="A big Teddy Bear", price="12€", wishlist_user=self.user
        )
        # Second user took one of the wishes
        self.assigned_wish = WishFactory.create(
            name="A pretty Barbie",
            wishlist_user=self.user,
            assigned_user=self.second_user,
        )

    def test_wishlist_user_creation(self):
        user = WishListUser.objects.create(
            name="Bob", is_admin=True, wishlist=self.wishlist
        )
        self.assertTrue(isinstance(user, WishListUser))

    def test_get_user_wishes(self):
        """Test that we correctly retrieve the user wishes"""
        # Create a second wish for the user
        second_wish = WishFactory.create(
            name="A big Teddy Bear 2", wishlist_user=self.user
        )

        # Wishes without an already assigned user
        wishes = self.user.get_user_wishes(already_assigned=False)
        self.assertEquals(len(wishes), 2)
        self.assertEquals(wishes[0].id, self.unassigned_wish.id)
        self.assertEquals(wishes[1].id, second_wish.id)

        # Wishes with an assigned user
        wishes = self.user.get_user_wishes(already_assigned=True)
        self.assertEquals(len(wishes), 1)
        self.assertEquals(wishes[0].id, self.assigned_wish.id)


class TestWish(SimpleWishlistBaseTestCase):
    def setUp(self):
        super().setUp()
        # Create Wishes for the user
        self.unassigned_wish = WishFactory.create(
            name="A big Teddy Bear", price="12€", wishlist_user=self.user
        )
        # Second user took one of the wishes
        self.assigned_wish = WishFactory.create(
            name="A pretty Barbie",
            wishlist_user=self.user,
            assigned_user=self.second_user,
        )

        self.wrong_user = WishListUserFactory(name="Gandalf", wishlist=self.wishlist)

    def assert_raises_validation_error(
        self, wish: Wish, candidate_assigned_user_id: UUID | None, current_user_id: UUID
    ):
        with self.assertRaisesRegex(
            SimpleWishlistValidationError, "Modifying assigned user unauthorized"
        ):
            # currently the "second user" is the one assigned to this wish and only him can change it
            wish.validate_assigned_user(
                # candidate_assigned_user_id comes from the request, so is a string
                candidate_assigned_user_id=str(candidate_assigned_user_id)
                if candidate_assigned_user_id
                else None,
                current_user_id=current_user_id,
            )

    def test_wish_creation(self):
        wish = Wish.objects.create(
            name="Wish Test", price="12€", wishlist_user=self.user
        )
        self.assertTrue(isinstance(wish, Wish))

    def test_validate_assigned_user_only_current_assigned_can_update(self):
        """Test that assigned user conditions"""

        # CASE 1: The user trying to change the assigned user is not the current assigned user
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_assigned_user_id=self.wrong_user.id,
            current_user_id=self.wrong_user.id,
        )

        # CASE 2: the wish owner is trying to change the assigned user
        # "user" is the owner of the wish, but he can not assign it to someone else
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_assigned_user_id=self.wrong_user.id,
            current_user_id=self.user.id,
        )

    def test_validate_assigned_user_remove_assigned_user(self):
        # CASE 3: the currently assigned user is trying to de-assigned himself
        # Should not raise exception
        response = self.assigned_wish.validate_assigned_user(
            candidate_assigned_user_id=None, current_user_id=self.second_user.id
        )
        self.assertTrue(response)

        # However, only the currently assigned user have the right to de-assign
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_assigned_user_id=None,
            current_user_id=self.user.id,
        )
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_assigned_user_id=None,
            current_user_id=self.wrong_user.id,
        )

    def test_validate_assigned_user_change_assigned_user_by_current_assigned_user(self):
        # The currently assigned user can only de-assigned himself and not assign it to someone else
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_assigned_user_id=self.wrong_user.id,
            current_user_id=self.second_user.id,
        )

    def test_validate_assigned_user_no_assigned_user_to_wish_owner(self):
        # CASE 4: No assigned user and the owner of the wish tries to assign himself
        self.assert_raises_validation_error(
            wish=self.unassigned_wish,
            candidate_assigned_user_id=self.user.id,
            current_user_id=self.user.id,
        )
        # Or someone else is trying
        self.assert_raises_validation_error(
            wish=self.unassigned_wish,
            candidate_assigned_user_id=self.user.id,
            current_user_id=self.wrong_user,
        )

    @patch.object(Wish, "validate_assigned_user", return_value=True)  # already tested
    def test_update_ok(self, validate_user_mock):
        # CASE 1: we change a field, everything should work fine
        update_data = WishModelUpdate(
            name="Another Name",
        ).dict(exclude_unset=True)

        self.unassigned_wish.update(
            current_user_id=self.user.id, update_data=update_data
        )
        self.unassigned_wish.refresh_from_db()
        self.assertEquals(self.unassigned_wish.name, update_data["name"])
        self.assertEquals(self.unassigned_wish.price, "12€")  # should not have changed

    @patch.object(Wish, "validate_assigned_user", return_value=True)  # already tested
    def test_update_only_owner_can_update(self, validate_user_mock):
        update_data = WishModelUpdate(
            name="Another Name",
        ).dict(exclude_unset=True)

        # CASE 2: someone else that the owner of the wish tried to change it
        with self.assertRaisesRegex(SimpleWishlistValidationError, "Only the owner"):
            self.unassigned_wish.update(
                current_user_id=self.second_user.id, update_data=update_data
            )

    @patch.object(Wish, "validate_assigned_user", return_value=True)  # already tested
    def test_update_assigned_user_does_not_exist(self, validate_user_mock):
        # CASE 3: The assigned user can only be updated if it exists
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        update_data = WishModelUpdate(
            assigned_user=str(fake_uuid),
        ).dict(exclude_unset=True)

        with self.assertRaisesRegex(SimpleWishlistValidationError, "does not exist."):
            self.unassigned_wish.update(
                current_user_id=self.user.id, update_data=update_data
            )

        # However, if it exists, the assignment should work
        update_data = WishModelUpdate(
            assigned_user=str(self.second_user.id),
        ).dict(exclude_unset=True)
        self.unassigned_wish.update(
            current_user_id=self.second_user.id, update_data=update_data
        )
        self.assertEquals(self.unassigned_wish.assigned_user, self.second_user)

    @patch.object(Wish, "validate_assigned_user", return_value=True)  # already tested
    def test_update_assign_to_none(self, validate_user_mock):
        # CASE 4: we want to assign to noone, it should work
        update_data = WishModelUpdate(
            assigned_user=None,
        ).dict(exclude_unset=True)
        self.unassigned_wish.update(
            current_user_id=self.second_user.id, update_data=update_data
        )
        self.assertEquals(self.unassigned_wish.assigned_user, None)
