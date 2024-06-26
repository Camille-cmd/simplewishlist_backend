from django.test import TestCase
from django.test.client import Client

from api.tests.factories import WishListFactory, WishListUserFactory


class SimpleWishlistBaseTestCase(TestCase):
    def setUp(self):
        self.wishlist = WishListFactory(wishlist_name="Test Wishlist")
        self.user = WishListUserFactory(name="Bob", wishlist=self.wishlist)
        self.second_user = WishListUserFactory(name="Alice", wishlist=self.wishlist)

        self.client = Client(headers={"Authorization": str(self.user.id)})
