import collections
from typing import Any, Optional

from ninja import Schema
from ninja.schema import DjangoGetter
from pydantic import UUID4, AnyHttpUrl, model_validator
from pydantic_core import PydanticCustomError


class WishlistInitModel(Schema):
    wishlist_name: str
    wishlist_admin_name: str
    allow_see_assigned: bool
    other_users_names: Optional[list[str]]

    @model_validator(mode="after")
    def no_two_same_names_validate(self):
        names = self.wishlist_admin_name, *self.other_users_names
        # Count the number of element in the list that appear more than once
        duplicated_names = [x for x, y in collections.Counter(names).items() if y > 1]
        if duplicated_names:
            raise PydanticCustomError(
                "identical_names_not_allowed",
                "Identical names detected. Names need to be different in order to differentiate people",
                dict(duplicated_names=set(duplicated_names)),
            )
        return self


class WishListWishModel(Schema):
    name: str
    price: Optional[str] = None
    url: Optional[str] = None
    id: Optional[UUID4] = None
    assigned_user: Optional[str] = None


class WishModel(Schema):
    """Wish creation"""

    name: str
    price: Optional[str] = None
    # TODO
    url: Optional[AnyHttpUrl | str] = None


class WishModelUpdate(WishModel):
    """Wish Update (all fields are optionals and we can add an assigned_user)"""

    name: Optional[str] = None
    assigned_user: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def check_whether_name_is_none(cls, data: DjangoGetter) -> Any:
        if hasattr(data, "name") and data.name is None:
            raise PydanticCustomError(
                "none_value_not_allowed",
                "Name can not be null",
            )
        return data


class WishListUserModel(Schema):
    user: str
    wishes: Optional[list[WishListWishModel]] = []


class WishListModel(Schema):
    wishListId: UUID4
    name: str
    allowSeeAssigned: bool
    currentUser: str
    isCurrentUserAdmin: bool
    userWishes: list[WishListUserModel]


class Message(Schema):
    message: str


class ErrorMessage(Schema):
    error: Message


class WebhookPayloadModel(Schema):
    type: str
    currentUser: UUID4
    post_values: Optional[dict] = {}
    objectId: Optional[UUID4] = None

    # todo validate if post_values is not None, then objectId should not be None
