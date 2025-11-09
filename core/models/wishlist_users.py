import uuid

from django.db import models


class WishListUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True, help_text="Is the user allowed to participate in the wishlist?")
    wishlist = models.ForeignKey("WishList", on_delete=models.CASCADE, related_name="wishlist_users")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Wishlist user"
        verbose_name_plural = "Wishlist users"
