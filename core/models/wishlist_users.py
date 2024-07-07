import uuid

from django.db import models

from api.pydantic_models import WishListWishModel


class WishListUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="Is the user allowed to participate in the wishlist?")
    wishlist = models.ForeignKey("WishList", on_delete=models.CASCADE, related_name="wishlist_users")

    def __str__(self):
        return self.name

    def get_user_wishes(self) -> [WishListWishModel]:
        """Return a Pydantic model containing the API response for User wishes"""
        wishes = []
        # We either return the wishes already assigned to someone, or not
        for wish in self.wishes.all():
            wishes.append(
                WishListWishModel(
                    name=wish.name,
                    price=wish.price or None,
                    url=wish.url or None,
                    id=wish.id,
                    assigned_user=wish.assigned_user.name if wish.assigned_user else None,
                )
            )
        return wishes

    class Meta:
        verbose_name = "Wishlist user"
        verbose_name_plural = "Wishlist users"
