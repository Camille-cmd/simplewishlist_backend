import json
import random
from uuid import UUID

from django.test.client import Client
from django.urls import reverse

from api.tests.factories import WishFactory
from api.tests.utils import SimpleWishlistBaseTestCase
from core.models import Wish, WishList, WishListUser


class TestWishListView(SimpleWishlistBaseTestCase):
    def test_get_wishlist(self):
        """Test returned data from the get wishlist view"""
        # Create Wishes for the user
        self.unassigned_wish = WishFactory.create(
            name="A big Teddy Bear", wishlist_user=self.user
        )
        # Second user took one of the wishes
        self.assigned_wish = WishFactory.create(
            name="A pretty Barbie",
            wishlist_user=self.user,
            assigned_user=self.second_user,
        )

        url = reverse("api-1.0.0:get_wishlist")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        expected_data = {
            "name": self.wishlist.wishlist_name,
            "allowSeeAssigned": False,
            "currentUser": self.user.name,
            "isCurrentUserAdmin": False,
            "userWishes": [
                {
                    "user": self.user.name,
                    "wishes": [
                        {
                            "name": self.unassigned_wish.name,
                            "price": self.unassigned_wish.price,
                            "url": self.unassigned_wish.url,
                            "id": str(self.unassigned_wish.id),
                            "assigned_user": None,
                        },
                    ],
                    "assignedWishes": [
                        {
                            "name": self.assigned_wish.name,
                            "price": self.assigned_wish.price,
                            "url": self.assigned_wish.url,
                            "id": str(self.assigned_wish.id),
                            "assigned_user": self.second_user.name,
                        }
                    ],
                },
                {"user": self.second_user.name, "wishes": [], "assignedWishes": []},
            ],
        }

        self.assertEquals(response.json(), expected_data)

    def test_put_wishlist(self):
        """Test that we can create the wishlist"""
        self.client = Client()  # only api call that does not need Authorization header
        wishlist_name = self.wishlist.wishlist_name
        data = {
            "wishlist_name": wishlist_name,
            "wishlist_admin_name": "Paul",
            "allow_see_assigned": True,
            "other_users_names": ["Peter", "Michelle", "Victor"],
        }
        url = reverse("api-1.0.0:create_wishlist")
        response = self.client.put(url, json.dumps(data))

        self.assertEqual(response.status_code, 200)

        expected_response = {
            "Paul": str(WishListUser.objects.get(name="Paul").id),
            "Peter": str(WishListUser.objects.get(name="Peter").id),
            "Michelle": str(WishListUser.objects.get(name="Michelle").id),
            "Victor": str(WishListUser.objects.get(name="Victor").id),
        }

        self.assertTrue(WishList.objects.filter(wishlist_name=wishlist_name).exists())
        self.assertEquals(response.json(), expected_response)


class TestWishView(SimpleWishlistBaseTestCase):
    def setUp(self):
        super().setUp()
        self.post_data = {
            "name": "Candy",
            "price": "12.45€",
            "url": "https://example.com/",
        }
        self.wish = WishFactory(
            name="A fast bike", price="120€", wishlist_user=self.user
        )

        self.view_url = reverse("api-1.0.0:create_wish")

        self.wish_view_url = reverse(
            "api-1.0.0:update_wish", kwargs={"wish_id": str(self.wish.id)}
        )

    def test_put_wish(self):
        """Test wish creation"""
        response = self.client.put(self.view_url, json.dumps(self.post_data))
        self.assertEqual(response.status_code, 201)

        # The response returns the wish id
        self.assertIsNotNone(response.json().get("wish"))

        wish_id = response.json()["wish"]
        wish = Wish.objects.get(id=wish_id)

        # Fields should be correctly set
        self.assertEquals(wish.name, self.post_data["name"])
        self.assertEquals(wish.price, self.post_data["price"])
        self.assertEquals(wish.url, self.post_data["url"])
        # Assigned user is always None on creation
        self.assertEquals(wish.assigned_user, None)

    def test_put_wish_current_user_does_not_exist(self):
        """Test that if the current user does not exist, we have a 404"""
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        client = Client(headers={"Authorization": f"bearer {str(fake_uuid)}"})
        response = client.put(self.view_url, json.dumps(self.post_data))
        self.assertEqual(response.status_code, 404)

    def test_post_wish(self):
        """Test wish update"""

        # Create a wish that we will update with an assigned user
        client = Client(headers={"Authorization": f"bearer {str(self.second_user.id)}"})
        data = {"assigned_user": str(self.second_user.id)}

        response = client.post(
            self.wish_view_url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)

        # Nothing except the assigned user should have changed
        self.wish.refresh_from_db()
        self.assertEquals(self.wish.name, "A fast bike")
        self.assertEquals(self.wish.price, "120€")
        self.assertEquals(self.wish.url, None)
        self.assertEquals(self.wish.assigned_user, self.second_user)

    def test_post_wish_wish_does_not_exist(self):
        """Test that if the wish does exist, a 404 is returned"""
        data = {"assigned_user": str(self.user.id)}
        # If the wish does not exist, we get a 404
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        view_url = reverse("api-1.0.0:update_wish", kwargs={"wish_id": str(fake_uuid)})
        response = self.client.post(
            view_url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 404)

    def test_post_wish_invalid_value(self):
        """Test that if a value is not valid, a 400 is returned"""
        data = {"name": 12}  # expects a str
        response = self.client.post(
            self.wish_view_url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 422)  # 422 = unprocessable entity
        self.assertEqual(response.json()["detail"][0]["type"], "string_type")

    def test_post_with_name_none(self):
        """Test value set to None"""
        data = {"name": None}
        response = self.client.post(
            self.wish_view_url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEquals(response.status_code, 422)

    def test_post_exclude_unset(self):
        """We do not want to keep unset values within the Pydantic model that wrongly would set value to None"""
        data = {"name": "Test"}
        response = self.client.post(
            self.wish_view_url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        self.wish.refresh_from_db()
        self.assertEquals(self.wish.name, "Test")
        self.assertEquals(self.wish.price, "120€")

    def test_delete_wish(self):
        """Test that we can correctly delete a wish"""
        # Create a wish that belongs to the second user
        wish = WishFactory(wishlist_user=self.second_user)
        view_url = reverse("api-1.0.0:delete_wish", kwargs={"wish_id": str(wish.id)})

        # With the first user, we try to delete, it should not be possible
        response = self.client.delete(view_url)
        self.assertEquals(response.status_code, 401)

        # With the second user, we try to delete. It should work as it is his wish
        client = Client(headers={"Authorization": f"bearer {str(self.second_user.id)}"})
        response = client.delete(view_url)
        self.assertEquals(response.status_code, 200)
