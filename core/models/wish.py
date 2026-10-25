import uuid

from django.db import IntegrityError, models

from api.exceptions import SimpleWishlistValidationError


class WishAssignment(models.Model):
    wish = models.ForeignKey("Wish", on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey("WishListUser", on_delete=models.CASCADE, related_name="wish_assignments")
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["wish", "user"], name="uniq_wish_assignment"),
        ]


class Wish(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    price = models.CharField(max_length=15, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    assigned_users = models.ManyToManyField(
        "WishListUser",
        through="WishAssignment",
        related_name="assigned_wishes",
        blank=True,
    )
    wishlist_user = models.ForeignKey(
        "WishListUser",
        on_delete=models.CASCADE,
        related_name="wishes",
        help_text="The wish belongs to this user",
    )
    suggested_by = models.ForeignKey(
        "WishListUser",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="suggested_wishes",
        help_text="The user who suggested this wish",
    )
    deleted = models.BooleanField(
        default=False,
    )

    def __str__(self):
        return f"Wish de {self.wishlist_user}"

    def get_assigned_user_names(self) -> list[str]:
        """Return the names of the users who took this wish, in the order they took it."""
        return list(
            WishAssignment.objects.filter(wish=self).order_by("assigned_at").values_list("user__name", flat=True)
        )

    def validate_assignment(self, candidate_user_id: str | None, current_user_id: uuid.UUID) -> None:
        """
        candidate_user_id: uuid (as str) of the user being added (take), or None (release).
        Raises SimpleWishlistValidationError on any violation.
        """
        if candidate_user_id is None:
            # Release: always allowed; removing a non-taker is a no-op (idempotent).
            return

        # Take:
        candidate_user_id = uuid.UUID(candidate_user_id)

        # Only self-assignment is accepted (same as today).
        if candidate_user_id != current_user_id:
            raise SimpleWishlistValidationError(
                model="Wish",
                field="assigned_user",
                message="Modifying assigned user unauthorized",
                code="wish_assignment_unauthorized",
            )
        # The owner can never take their own wish.
        if candidate_user_id == self.wishlist_user.id:
            raise SimpleWishlistValidationError(
                model="Wish",
                field="assigned_user",
                message="Modifying assigned user unauthorized",
                code="wish_assignment_unauthorized",
            )
        # A soft-deleted wish cannot be taken.
        if self.deleted:
            raise SimpleWishlistValidationError(
                model="Wish",
                field="assigned_user",
                message="This wish has been deleted.",
                code="wish_deleted",
            )
        # A user can take a wish at most once.
        if self.assigned_users.filter(id=current_user_id).exists():
            raise SimpleWishlistValidationError(
                model="Wish",
                field="assigned_user",
                message="You have already taken this wish.",
                code="wish_already_taken",
            )

    def update(self, current_user_id: uuid.UUID, update_data: dict) -> bool:
        """
        A wish can be changed only by its owner except for the field assigned_user which should be
        changed only by others
        Returns True if the wish was permanently deleted during the update.
        """
        from core.models import WishListUser

        for attr, value in update_data.items():
            if attr == "assigned_user":
                # validation of assigned user
                self.validate_assignment(candidate_user_id=value, current_user_id=current_user_id)
                if value:
                    # Take: add self.
                    try:
                        user = WishListUser.objects.get(id=value)
                    except WishListUser.DoesNotExist:
                        raise SimpleWishlistValidationError(
                            model="Wish",
                            field="assigned_user",
                            message="The user the wish is being assigned to does not exist.",
                            code="wish_assignment_user_not_found",
                        )
                    try:
                        self.assigned_users.add(user)
                    except IntegrityError:
                        # Defensive: unique (wish, user) constraint (double-click etc.)
                        raise SimpleWishlistValidationError(
                            model="Wish",
                            field="assigned_user",
                            message="You have already taken this wish.",
                            code="wish_already_taken",
                        )
                else:
                    # Release: remove self (no-op if not a taker).
                    self.assigned_users.remove(WishListUser.objects.get(id=current_user_id))
                    # If the wish was soft-deleted and no takers remain, delete permanently.
                    if self.deleted and not self.assigned_users.exists():
                        self.delete()
                        # Return now we do not want to save
                        return True
            else:
                # Check edit permissions based on whether it's a suggested wish or regular wish
                # Suggested wish: only suggester can edit
                # Regular wish: only owner can edit
                if self.suggested_by is not None:
                    # Suggested wish
                    if current_user_id != self.suggested_by.id:
                        raise SimpleWishlistValidationError(
                            model="Wish",
                            field=attr,
                            message="Only the suggester can edit this suggested wish.",
                            code="wish_suggested_edit_unauthorized",
                        )
                else:
                    # Regular wish
                    if current_user_id != self.wishlist_user.id:
                        raise SimpleWishlistValidationError(
                            model="Wish",
                            field=attr,
                            message="Only the owner of the wish can change the wish data.",
                            code="wish_edit_unauthorized",
                        )

                setattr(self, attr, value)

            self.save()

        return False

    def mark_deleted(self):
        """
        If no user is assigned to the wish, we can delete it.
        But if a user is assigned to it, just mark it as deleted, we want him/her to be able to see it.
        """
        if self.assigned_users.exists():
            self.deleted = True
            self.save()
        else:
            self.delete()

    def can_be_deleted(self, current_user_id: uuid.UUID) -> tuple[bool, str, str]:
        """
        Check if the wish can be deleted
        Regular wishes: only the owner can delete
        Suggested wishes: only the suggester can delete
        Returns (can_be_deleted, code, message)
        """
        # Suggested wish: only suggester can delete
        if self.suggested_by is not None:
            if self.suggested_by.id != current_user_id:
                return False, "wish_suggested_delete_unauthorized", "Only the suggester can delete this suggested wish."
            return True, "", ""

        # Regular wish: only owner can delete
        if self.wishlist_user.id != current_user_id:
            return False, "wish_delete_unauthorized", "Only the owner of the wish can delete it."

        return True, "", ""

    class Meta:
        verbose_name_plural = "wishes"
