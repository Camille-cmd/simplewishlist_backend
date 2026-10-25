from django.core.management import call_command
from django.db.migrations.loader import MigrationLoader
from django.test import TransactionTestCase

from core.models import WishAssignment


class TestBackfillWishAssignments(TransactionTestCase):
    """Test the backfill data migration that moves Wish.assigned_user into WishAssignment rows."""

    def test_backfill_creates_assignment_rows(self):
        # Roll back to the migration state where Wish.assigned_user still exists
        call_command("migrate", "core", "0010_wishassignment", verbosity=0)
        try:
            # Historical models from the migration state where assigned_user still exists
            state = MigrationLoader(None).project_state([("core", "0010_wishassignment")])
            historical_wish_list = state.apps.get_model("core", "WishList")
            historical_wish_list_user = state.apps.get_model("core", "WishListUser")
            historical_wish = state.apps.get_model("core", "Wish")

            wishlist = historical_wish_list.objects.create(wishlist_name="Backfill wishlist")
            owner = historical_wish_list_user.objects.create(name="Owner", wishlist=wishlist)
            taker = historical_wish_list_user.objects.create(name="Taker", wishlist=wishlist)

            assigned_wish = historical_wish.objects.create(
                name="Assigned wish",
                wishlist_user=owner,
                assigned_user=taker,
            )
            historical_wish.objects.create(name="Unassigned wish", wishlist_user=owner)

            # Run the backfill data migration
            call_command("migrate", "core", "0011_backfill_wish_assignments", verbosity=0)

            # One WishAssignment row per previously assigned wish, none for the unassigned one
            self.assertEqual(WishAssignment.objects.count(), 1)
            assignment = WishAssignment.objects.get()
            self.assertEqual(assignment.wish_id, assigned_wish.id)
            self.assertEqual(assignment.user_id, taker.id)
        finally:
            # Restore the final migration state
            call_command("migrate", "core", verbosity=0)
