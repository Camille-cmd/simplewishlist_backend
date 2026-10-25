import threading
from uuid import UUID

from django.test import TransactionTestCase

from api.exceptions import SimpleWishlistValidationError
from api.pydantic_models import WishModelUpdate
from api.tests.factories import WishFactory, WishListFactory, WishListUserFactory
from api.tests.utils import SimpleWishlistBaseTestCase
from core.models import Wish, WishAssignment, WishListUser


class TestWishListUser(SimpleWishlistBaseTestCase):
    def setUp(self):
        super().setUp()
        # Create Wishes for the user
        self.unassigned_wish = WishFactory.create(name="A big Teddy Bear", price="12€", wishlist_user=self.user)
        # Second user took one of the wishes
        self.assigned_wish = WishFactory.create(name="A pretty Barbie", wishlist_user=self.user)
        self.assigned_wish.assigned_users.add(self.second_user)

    def test_wishlist_user_creation(self):
        user = WishListUser.objects.create(name="Bob", wishlist=self.wishlist)
        self.assertTrue(isinstance(user, WishListUser))


class TestWish(SimpleWishlistBaseTestCase):
    def setUp(self):
        super().setUp()
        # Create Wishes for the user
        self.unassigned_wish = WishFactory.create(name="A big Teddy Bear", price="12€", wishlist_user=self.user)
        # Second user took one of the wishes
        self.assigned_wish = WishFactory.create(name="A pretty Barbie", wishlist_user=self.user)
        self.assigned_wish.assigned_users.add(self.second_user)

        self.wrong_user = WishListUserFactory(name="Gandalf", wishlist=self.wishlist)

    def assert_raises_validation_error(
        self, wish: Wish, candidate_user_id: UUID | None, current_user_id: UUID, message: str
    ):
        with self.assertRaisesRegex(SimpleWishlistValidationError, message):
            wish.validate_assignment(
                # candidate_user_id comes from the request, so is a string
                candidate_user_id=str(candidate_user_id) if candidate_user_id else None,
                current_user_id=current_user_id,
            )

    def test_wish_creation(self):
        wish = Wish.objects.create(name="Wish Test", price="12€", wishlist_user=self.user)
        self.assertTrue(isinstance(wish, Wish))

    # --- validate_assignment ---

    def test_validate_assignment_self_take_allowed(self):
        # Any non-owner may take a wish, even one already taken by someone else (multi-assignment)
        self.assigned_wish.validate_assignment(
            candidate_user_id=str(self.wrong_user.id), current_user_id=self.wrong_user.id
        )

    def test_validate_assignment_cannot_assign_other_user(self):
        # The API only ever accepts self-assignment: candidate must equal the current user
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_user_id=self.wrong_user.id,
            current_user_id=self.user.id,
            message="Modifying assigned user unauthorized",
        )

    def test_validate_assignment_owner_cannot_take_own_wish(self):
        # The owner of a regular wish can never take it
        self.assert_raises_validation_error(
            wish=self.unassigned_wish,
            candidate_user_id=self.user.id,
            current_user_id=self.user.id,
            message="Modifying assigned user unauthorized",
        )
        # ...nor the owner of a suggested wish
        suggested_wish = WishFactory.create(wishlist_user=self.second_user, suggested_by=self.user)
        self.assert_raises_validation_error(
            wish=suggested_wish,
            candidate_user_id=self.second_user.id,
            current_user_id=self.second_user.id,
            message="Modifying assigned user unauthorized",
        )

    def test_validate_assignment_soft_deleted_wish_cannot_be_taken(self):
        self.assigned_wish.deleted = True
        self.assigned_wish.save()
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_user_id=self.wrong_user.id,
            current_user_id=self.wrong_user.id,
            message="This wish has been deleted.",
        )

    def test_validate_assignment_already_taken(self):
        # A user can take a wish at most once
        self.assert_raises_validation_error(
            wish=self.assigned_wish,
            candidate_user_id=self.second_user.id,
            current_user_id=self.second_user.id,
            message="You have already taken this wish.",
        )

    def test_validate_assignment_release_always_allowed(self):
        # Release by a taker is allowed
        self.assigned_wish.validate_assignment(candidate_user_id=None, current_user_id=self.second_user.id)
        # Release by a non-taker is a no-op and must not raise
        self.assigned_wish.validate_assignment(candidate_user_id=None, current_user_id=self.user.id)

    # --- update() ---

    def test_two_users_can_take_the_same_wish(self):
        # Alice already took the wish (setUp); a third user joins (the owner can never take it)
        self.assigned_wish.update(
            current_user_id=self.wrong_user.id, update_data={"assigned_user": str(self.wrong_user.id)}
        )
        self.assigned_wish.refresh_from_db()
        self.assertEqual(set(self.assigned_wish.assigned_users.all()), {self.second_user, self.wrong_user})

    def test_same_user_cannot_take_twice(self):
        with self.assertRaisesRegex(SimpleWishlistValidationError, "You have already taken this wish."):
            self.assigned_wish.update(
                current_user_id=self.second_user.id, update_data={"assigned_user": str(self.second_user.id)}
            )
        self.assertEqual(self.assigned_wish.assigned_users.count(), 1)

    def test_release_by_non_taker_is_noop(self):
        # Bob is not a taker of assigned_wish (only Alice is)
        self.assigned_wish.update(current_user_id=self.user.id, update_data={"assigned_user": None})
        self.assigned_wish.refresh_from_db()
        self.assertEqual(list(self.assigned_wish.assigned_users.all()), [self.second_user])

    def test_release_by_taker_removes_only_that_taker(self):
        # Both Alice and Gandalf take the wish
        self.assigned_wish.update(
            current_user_id=self.wrong_user.id, update_data={"assigned_user": str(self.wrong_user.id)}
        )
        # Alice releases
        self.assigned_wish.update(current_user_id=self.second_user.id, update_data={"assigned_user": None})
        self.assigned_wish.refresh_from_db()
        self.assertEqual(list(self.assigned_wish.assigned_users.all()), [self.wrong_user])

    def test_last_taker_release_soft_deleted_wish_hard_deletes(self):
        self.assigned_wish.deleted = True
        self.assigned_wish.save()
        self.assigned_wish.update(current_user_id=self.second_user.id, update_data={"assigned_user": None})
        with self.assertRaises(Wish.DoesNotExist):
            self.assigned_wish.refresh_from_db()

    def test_non_last_taker_release_soft_deleted_wish_stays(self):
        # Both Alice and Gandalf take the wish, then it is soft-deleted
        self.assigned_wish.update(
            current_user_id=self.wrong_user.id, update_data={"assigned_user": str(self.wrong_user.id)}
        )
        self.assigned_wish.deleted = True
        self.assigned_wish.save()
        # Alice releases; Gandalf remains, so the wish stays soft-deleted
        self.assigned_wish.update(current_user_id=self.second_user.id, update_data={"assigned_user": None})
        self.assigned_wish.refresh_from_db()
        self.assertTrue(self.assigned_wish.deleted)
        self.assertEqual(list(self.assigned_wish.assigned_users.all()), [self.wrong_user])

    def test_update_ok(self):
        # The owner changes a field, everything should work fine
        update_data = WishModelUpdate(name="Another Name").dict(exclude_unset=True)
        self.unassigned_wish.update(current_user_id=self.user.id, update_data=update_data)
        self.unassigned_wish.refresh_from_db()
        self.assertEqual(self.unassigned_wish.name, update_data["name"])
        self.assertEqual(self.unassigned_wish.price, "12€")  # should not have changed

    def test_update_only_owner_can_update(self):
        update_data = WishModelUpdate(name="Another Name").dict(exclude_unset=True)
        # Someone else than the owner of the wish tries to change it
        with self.assertRaisesRegex(SimpleWishlistValidationError, "Only the owner"):
            self.unassigned_wish.update(current_user_id=self.second_user.id, update_data=update_data)

    def test_update_assigned_user_does_not_exist(self):
        # The assigned user can only be updated if it exists.
        # The candidate must be the current user (self-assignment only), so we delete
        # a real user and try to assign the wish to that now-missing user.
        ghost = WishListUserFactory(name="Ghost", wishlist=self.wishlist)
        ghost_id = ghost.id
        ghost.delete()
        with self.assertRaisesRegex(SimpleWishlistValidationError, "does not exist."):
            self.unassigned_wish.update(current_user_id=ghost_id, update_data={"assigned_user": str(ghost_id)})

        # However, if it exists, the assignment should work
        self.unassigned_wish.update(
            current_user_id=self.second_user.id, update_data={"assigned_user": str(self.second_user.id)}
        )
        self.unassigned_wish.refresh_from_db()
        self.assertIn(self.second_user, self.unassigned_wish.assigned_users.all())

    def test_update_assign_to_none(self):
        # Releasing a wish we never took is a no-op
        self.unassigned_wish.update(current_user_id=self.second_user.id, update_data={"assigned_user": None})
        self.unassigned_wish.refresh_from_db()
        self.assertEqual(self.unassigned_wish.assigned_users.count(), 0)

    def test_suggester_can_edit_suggested_wish(self):
        suggested_wish = WishFactory.create(wishlist_user=self.second_user, suggested_by=self.user)
        suggested_wish.update(current_user_id=self.user.id, update_data={"name": "New name"})
        suggested_wish.refresh_from_db()
        self.assertEqual(suggested_wish.name, "New name")

    def test_owner_cannot_edit_suggested_wish(self):
        suggested_wish = WishFactory.create(wishlist_user=self.second_user, suggested_by=self.user)
        with self.assertRaisesRegex(SimpleWishlistValidationError, "Only the suggester can edit"):
            suggested_wish.update(current_user_id=self.second_user.id, update_data={"name": "New name"})

    # --- mark_deleted / can_be_deleted ---

    def test_mark_deleted_with_takers_soft_deletes(self):
        self.assigned_wish.mark_deleted()
        self.assigned_wish.refresh_from_db()
        self.assertTrue(self.assigned_wish.deleted)

    def test_mark_deleted_without_takers_hard_deletes(self):
        self.unassigned_wish.mark_deleted()
        with self.assertRaises(Wish.DoesNotExist):
            self.unassigned_wish.refresh_from_db()

    def test_can_be_deleted_by_owner(self):
        can, code, message = self.unassigned_wish.can_be_deleted(self.user.id)
        self.assertTrue(can)
        self.assertEqual(code, "")

    def test_can_not_be_deleted_by_non_owner(self):
        can, code, message = self.unassigned_wish.can_be_deleted(self.second_user.id)
        self.assertFalse(can)
        self.assertEqual(code, "wish_delete_unauthorized")
        self.assertEqual(message, "Only the owner of the wish can delete it.")

    def test_can_be_deleted_suggested_by_suggester(self):
        suggested_wish = WishFactory.create(wishlist_user=self.second_user, suggested_by=self.user)
        can, code, message = suggested_wish.can_be_deleted(self.user.id)
        self.assertTrue(can)
        self.assertEqual(code, "")

    def test_can_not_be_deleted_suggested_by_owner(self):
        suggested_wish = WishFactory.create(wishlist_user=self.second_user, suggested_by=self.user)
        can, code, message = suggested_wish.can_be_deleted(self.second_user.id)
        self.assertFalse(can)
        self.assertEqual(code, "wish_suggested_delete_unauthorized")
        self.assertEqual(message, "Only the suggester can delete this suggested wish.")


class TestWishConcurrency(TransactionTestCase):
    """
    Concurrency tests for take/release on the same wish.

    These use TransactionTestCase (no wrapping transaction) so that the worker
    threads see the committed setup data and each runs in its own connection/transaction.
    """

    def setUp(self):
        super().setUp()
        self.wishlist = WishListFactory(wishlist_name="Test Wishlist")
        self.owner = WishListUserFactory(name="Owner", wishlist=self.wishlist)
        self.user = WishListUserFactory(name="Bob", wishlist=self.wishlist)
        self.other_user = WishListUserFactory(name="Gandalf", wishlist=self.wishlist)
        self.wish = WishFactory.create(name="Contended wish", wishlist_user=self.owner)

    def test_same_user_double_take_results_in_single_assignment(self):
        barrier = threading.Barrier(2)
        errors = []

        def take():
            try:
                barrier.wait()
                self.wish.update(current_user_id=self.user.id, update_data={"assigned_user": str(self.user.id)})
            except SimpleWishlistValidationError as e:
                errors.append(e)

        threads = [threading.Thread(target=take) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly one assignment row, and exactly one friendly validation error
        self.assertEqual(WishAssignment.objects.filter(wish=self.wish, user=self.user).count(), 1)
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].code, "wish_already_taken")

    def test_take_vs_last_release_race_on_soft_deleted_wish(self):
        # Bob is the only taker and the wish is soft-deleted
        self.wish.assigned_users.add(self.user)
        self.wish.deleted = True
        self.wish.save()

        barrier = threading.Barrier(2)
        results = {"take_error": None, "release_error": None}

        def take():
            try:
                barrier.wait()
                self.wish.update(
                    current_user_id=self.other_user.id, update_data={"assigned_user": str(self.other_user.id)}
                )
            except (SimpleWishlistValidationError, Wish.DoesNotExist) as e:
                results["take_error"] = e

        def release():
            try:
                barrier.wait()
                self.wish.update(current_user_id=self.user.id, update_data={"assigned_user": None})
            except Exception as e:  # noqa: BLE001 - we assert it is None below
                results["release_error"] = e

        threads = [threading.Thread(target=take), threading.Thread(target=release)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # The release must succeed; the take must fail (wish_deleted or DoesNotExist)
        self.assertIsNone(results["release_error"])
        self.assertIsNotNone(results["take_error"])
        # The consistent outcome: the wish is hard-deleted in the end
        with self.assertRaises(Wish.DoesNotExist):
            Wish.objects.get(pk=self.wish.pk)


class TestWishList(SimpleWishlistBaseTestCase):
    def setUp(self):
        super().setUp()
        self.inactive_user = WishListUserFactory(name="Inactive", wishlist=self.wishlist, is_active=False)

    def test_only_active_users_are_returned(self):
        active_users = self.wishlist.get_active_users()
        self.assertIn(self.user, active_users)
        self.assertNotIn(self.inactive_user, active_users)
