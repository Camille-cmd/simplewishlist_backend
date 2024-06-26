import uuid

from django.db import models


class WishList(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist_name = models.CharField(max_length=100)
    show_users = models.BooleanField(default=False)

    def __str__(self):
        return f"Wishlist: {self.wishlist_name}"

    class Meta:
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"
