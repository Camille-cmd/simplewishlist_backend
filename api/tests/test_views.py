import json
import random
from uuid import UUID

from django.test.client import Client
from django.urls import reverse

from api.tests.factories import WishFactory
from api.tests.utils import SimpleWishlistBaseTestCase
from core.models import WishList, WishListUser


class TestWishListView(SimpleWishlistBaseTestCase):
    """Test the wishlist api views"""

    def test_get_wishlist_settings(self):
        """Test returned data from the get wishlist view"""
        # Create Wishes for the user
        self.unassigned_wish = WishFactory.create(name="A big Teddy Bear", wishlist_user=self.user)
        # Second user took one of the wishes
        self.assigned_wish = WishFactory.create(
            name="A pretty Barbie",
            wishlist_user=self.user,
            assigned_user=self.second_user,
        )

        url = reverse("api-1.0.0:get_wishlist_settings")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        expected_data = {
            "wishlistName": self.wishlist.wishlist_name,
            "allowSeeAssigned": False,
        }

        self.assertEqual(response.json(), expected_data)

    def test_put_wishlist(self):
        """Test that we can create the wishlist"""
        client = Client()  # only api call that does not need Authorization header
        wishlist_name = self.wishlist.wishlist_name
        data = {
            "wishlist_name": wishlist_name,
            "wishlist_admin_name": "Paul",
            "allow_see_assigned": True,
            "other_users_names": ["Peter", "Michelle", "Victor"],
        }
        url = reverse("api-1.0.0:create_wishlist")
        response = client.put(url, json.dumps(data))

        self.assertEqual(response.status_code, 200)

        expected_response = [
            {"id": str(WishListUser.objects.get(name="Paul").id), "name": "Paul", "isAdmin": True, "isActive": True},
            {"id": str(WishListUser.objects.get(name="Peter").id), "name": "Peter", "isAdmin": False, "isActive": True},
            {
                "id": str(WishListUser.objects.get(name="Michelle").id),
                "name": "Michelle",
                "isAdmin": False,
                "isActive": True,
            },
            {
                "id": str(WishListUser.objects.get(name="Victor").id),
                "name": "Victor",
                "isAdmin": False,
                "isActive": True,
            },
        ]

        self.assertTrue(WishList.objects.filter(wishlist_name=wishlist_name).exists())
        self.assertEqual(response.json(), expected_response)

    def test_put_wishlist_duplicated_names(self):
        """Test that we cannot create a wishlist with duplicated names"""
        client = Client()
        data = {
            "wishlist_name": "Wishlist",
            "wishlist_admin_name": "Paul",
            "allow_see_assigned": True,
            "other_users_names": ["Paul", "Michelle", "Victor"],
        }
        url = reverse("api-1.0.0:create_wishlist")
        response = client.put(url, json.dumps(data))

        self.assertEqual(response.status_code, 422)

    def test_update_wishlist(self):
        """Test that we can update the wishlist"""
        data = {
            "wishlist_name": "New Wishlist Name",
            "allow_see_assigned": True,
        }
        url = reverse("api-1.0.0:update_wishlist")
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        # The response should return the new data
        self.assertEqual(response.json(), {"wishlistName": "New Wishlist Name", "allowSeeAssigned": True})

    def test_update_wishlist_not_admin(self):
        """Test that a non-admin cannot update the wishlist"""
        data = {
            "wishlist_name": "New Wishlist Name",
            "allow_see_assigned": True,
        }
        client = Client(headers={"Authorization": f"bearer {str(self.second_user.id)}"})
        url = reverse("api-1.0.0:update_wishlist")
        response = client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 401)

    def test_get_wishlist_users(self):
        """Test that we can get the wishlist users"""
        url = reverse("api-1.0.0:get_wishlist_users")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        expected_data = [
            {
                "id": str(self.second_user.id),
                "name": self.second_user.name,
                "isAdmin": False,
                "isActive": True,
            },
            {
                "id": str(self.user.id),
                "name": self.user.name,
                "isAdmin": True,
                "isActive": True,
            }
        ]
        self.assertEqual(response.json(), expected_data)

    def test_deactivate_user(self):
        """Test that we can deactivate a user"""
        url = reverse("api-1.0.0:deactivate_user", kwargs={"user_id": str(self.second_user.id)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(WishListUser.objects.get(id=self.second_user.id).is_active)

    def test_deactivate_user_not_admin(self):
        """Test that a non-admin cannot deactivate a user"""
        client = Client(headers={"Authorization": f"bearer {str(self.second_user.id)}"})
        url = reverse("api-1.0.0:deactivate_user", kwargs={"user_id": str(self.user.id)})
        response = client.post(url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["message"], "Only the admin can deactivate a user")
        # The user should still be active
        self.assertTrue(WishListUser.objects.get(id=self.user.id).is_active)

    def test_deactivate_user_admin(self):
        """Test that we cannot deactivate the admin"""
        url = reverse("api-1.0.0:deactivate_user", kwargs={"user_id": str(self.user.id)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["message"], "The admin can not be deactivated")
        # The user should still be active
        self.assertTrue(WishListUser.objects.get(id=self.user.id).is_active)

    def test_deactivate_user_not_found(self):
        """Test that we cannot deactivate a user that does not exist"""
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        url = reverse("api-1.0.0:deactivate_user", kwargs={"user_id": str(fake_uuid)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

    def test_activate_user(self):
        """Test that we can activate a user"""
        # Deactivate the user first
        self.second_user.is_active = False
        self.second_user.save()

        url = reverse("api-1.0.0:activate_user", kwargs={"user_id": str(self.second_user.id)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(WishListUser.objects.get(id=self.second_user.id).is_active)

    def test_activate_user_not_admin(self):
        """Test that a non-admin cannot activate a user"""
        self.user.is_active = False
        self.user.save()

        client = Client(headers={"Authorization": f"bearer {str(self.second_user.id)}"})
        url = reverse("api-1.0.0:activate_user", kwargs={"user_id": str(self.user.id)})
        response = client.post(url)
        self.assertEqual(response.json()["error"]["message"], "Only the admin can activate a user")
        # The user should still be inactive
        self.assertFalse(WishListUser.objects.get(id=self.user.id).is_active)

    def test_activate_user_not_found(self):
        """Test that we cannot activate a user that does not exist"""
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        url = reverse("api-1.0.0:activate_user", kwargs={"user_id": str(fake_uuid)})
        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)

    def test_add_new_user_to_wishlist(self):
        """Test that we can create a new user"""
        data = {"name": "Paul"}
        url = reverse("api-1.0.0:add_new_user_to_wishlist")
        response = self.client.put(url, json.dumps(data))

        self.assertEqual(response.status_code, 201)
        self.assertTrue(WishListUser.objects.filter(name="Paul").exists())

    def test_add_new_user_to_wishlist_not_by_admin(self):
        """Test that a user that is not an admin cannot add a new user"""
        # Second user is not an admin
        client = Client(headers={"Authorization": f"bearer {str(self.second_user.id)}"})
        data = {"name": "Paul"}
        url = reverse("api-1.0.0:add_new_user_to_wishlist")
        response = client.put(url, json.dumps(data))

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["message"], "Only the admin can add a user")

    def test_add_new_user_to_wishlist_duplicated(self):
        """Test that we cannot create a new user with the same name"""
        data = {"name": self.user.name}
        url = reverse("api-1.0.0:add_new_user_to_wishlist")
        response = self.client.put(url, json.dumps(data))

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["message"], "User already exists in the wishlist")

    def test_update_user(self):
        """Test that we can update a user"""
        data = {"name": "New Name"}
        # Make sure the user's name is not already the new name
        self.assertFalse(self.user.name == "New Name")

        url = reverse("api-1.0.0:update_user_in_wishlist", kwargs={"user_id": str(self.user.id)})
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"id": str(self.user.id), "name": "New Name", "isAdmin": True, "isActive": True}
        )

    def test_update_user_not_admin(self):
        """Test that a non-admin cannot update a user"""
        data = {"name": "New Name"}
        client = Client(headers={"Authorization": f"bearer {str(self.second_user.id)}"})
        url = reverse("api-1.0.0:update_user_in_wishlist", kwargs={"user_id": str(self.user.id)})
        response = client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 401)

    def test_update_user_not_found(self):
        """Test that we cannot update a user that does not exist"""
        fake_uuid = UUID(int=random.getrandbits(128), version=4)
        data = {"name": "New Name"}
        url = reverse("api-1.0.0:update_user_in_wishlist", kwargs={"user_id": str(fake_uuid)})
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 404)

    def test_update_user_duplicated(self):
        """Test that we cannot update a user with a name that already exists"""
        data = {"name": self.second_user.name}
        url = reverse("api-1.0.0:update_user_in_wishlist", kwargs={"user_id": str(self.user.id)})
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["message"], "User already exists in the wishlist")

    def test_update_user_same_name(self):
        """Test that we can update a user with the same name as before"""
        data = {"name": self.user.name}
        url = reverse("api-1.0.0:update_user_in_wishlist", kwargs={"user_id": str(self.user.id)})
        response = self.client.post(url, data=json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"id": str(self.user.id), "name": self.user.name, "isAdmin": True, "isActive": True}
        )
