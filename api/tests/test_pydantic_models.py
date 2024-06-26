from pydantic_core import ValidationError

from api.pydantic_models import WishlistInitModel, WishModelUpdate
from api.tests.utils import SimpleWishlistBaseTestCase


class TestWishlistInitModel(SimpleWishlistBaseTestCase):
    pydantic_model = WishlistInitModel

    def test_no_two_same_names_validate_validation(self):
        """Validate that no two users can have the same name"""

        # We have two users with the same name, il should raise a ValidationError
        data = {
            "wishlist_name": "Noël",
            "wishlist_admin_name": "Tom",
            "allow_see_assigned": True,
            "other_users_names": ["Tom", "John", "Maggie"],
        }

        with self.assertRaisesRegex(ValidationError, "Identical names detected"):
            self.pydantic_model(**data)


class TestWishModelUpdate(SimpleWishlistBaseTestCase):
    pydantic_model = WishModelUpdate

    def test_check_whether_name_is_none(self):
        """When name is None, it should raise an exception"""
        data = {
            "name": None,
            "price": "12€",
        }

        with self.assertRaisesRegex(ValidationError, "Name can not be null"):
            self.pydantic_model(**data)
