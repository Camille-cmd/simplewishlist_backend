import uuid

from django.db import models

from api.exceptions import SimpleWishlistValidationError


class Wish(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    price = models.CharField(max_length=10, blank=True, null=True)
    url = models.URLField(blank=True, null=True)
    assigned_user = models.ForeignKey(
        "WishListUser",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="assigned_wishes",
    )
    wishlist_user = models.ForeignKey(
        "WishListUser",
        on_delete=models.CASCADE,
        related_name="wishes",
        help_text="The wish belongs to this user",
    )

    def __str__(self):
        return f"Wish de {self.wishlist_user}"

    def validate_assigned_user(self, candidate_assigned_user_id: str | None, current_user_id: uuid.UUID) -> bool:
        """Validate the candidate_assigned_user change conditions"""
        currently_assigned_user = self.assigned_user

        # We are not trying to change anything
        if not candidate_assigned_user_id and not currently_assigned_user:
            return True

        # Compare UUID with UUID
        if candidate_assigned_user_id is not None:
            candidate_assigned_user_id = uuid.UUID(candidate_assigned_user_id)

        # Only the current candidate_assigned_user can change the candidate_assigned_user
        # one can de-assigned oneself but no one else can
        if (
            not currently_assigned_user  # no assigned user yet
            and candidate_assigned_user_id != self.wishlist_user.id  # candidate user is not the owner of the wish
            and candidate_assigned_user_id == current_user_id  # only the current user can assign himself
        ):
            return True

        # de-assigned (assigned user already exists, but he wants to remove himself)
        if not candidate_assigned_user_id and currently_assigned_user.id == current_user_id:
            return True

        raise SimpleWishlistValidationError(
            model="Wish",
            field="assigned_user",
            message="Modifying assigned user unauthorized",
        )

    def update(self, current_user_id: uuid.UUID, update_data: dict) -> None:
        """
        A wish can be changed only by its owner except for the field assigned_user which should be
        changed only by others
        """
        from core.models import WishListUser

        # Dynamic update of the instance fields
        for attr, value in update_data.items():
            if attr == "assigned_user":
                # validation of assigned user
                self.validate_assigned_user(candidate_assigned_user_id=value, current_user_id=current_user_id)

                try:
                    # For the assigned user, we need to get the WishListUser object
                    if value:
                        user = WishListUser.objects.get(id=value)
                        self.assigned_user = user
                    else:
                        self.assigned_user = None

                except WishListUser.DoesNotExist:
                    raise SimpleWishlistValidationError(
                        model="Wish",
                        field="assigned_user",
                        message="The user the wish is being assigned to does not exist.",
                    )

            else:
                # check that the user trying to change things is the owner of the wish
                if current_user_id != self.wishlist_user.id:
                    raise SimpleWishlistValidationError(
                        model="Wish",
                        field=value,
                        message="Only the owner of the wish can change the wish data.",
                    )

                setattr(self, attr, value)

        self.save()

    class Meta:
        verbose_name_plural = "wishes"
        ordering = ["-id"]
