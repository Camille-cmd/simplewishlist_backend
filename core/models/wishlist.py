import uuid

from django.db import models


class WishList(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wishlist_name = models.CharField(max_length=100)
    is_surprise_mode_enabled = models.BooleanField(default=True)
    show_users = models.BooleanField(default=False)

    def __str__(self):
        return f"Wishlist: {self.wishlist_name}"

    def get_active_users(self):
        """Return the users of the wishlist that are still active and allowed to participate"""
        return self.wishlist_users.filter(is_active=True).order_by("name")

    def get_users(self, exclude_users_ids: list = None):
        """Return all the users of the wishlist"""
        if exclude_users_ids is None:
            exclude_users_ids = []
        return self.wishlist_users.order_by("name", "-is_active").exclude(id__in=exclude_users_ids)

    def get_admin(self):
        """Return the admin of the wishlist"""
        return self.wishlist_users.get(is_admin=True)

    class Meta:
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"
