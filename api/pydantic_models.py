import collections
from typing import Any, Optional

from ninja import Schema
from ninja.schema import DjangoGetter
from pydantic import UUID4, model_validator, AnyUrl, field_validator, field_serializer
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError
from pydantic_core.core_schema import ValidationInfo


class BaseSchema(Schema):
    class Config(Schema.Config):
        populate_by_name = True
        alias_generator = to_camel


class WishlistInitModel(BaseSchema):
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
                dict(duplicated_names=list(set(duplicated_names))),
            )
        return self


class WishListWishModel(BaseSchema):
    name: str
    deleted: bool
    price: Optional[str] = None
    url: Optional[AnyUrl] = None
    description: Optional[str] = None
    id: Optional[UUID4] = None
    assigned_user: Optional[str] = None

    @field_serializer("url")
    def serialize_url(self, url: AnyUrl):
        # Pydantic does not serialize AnyUrl into str.
        # We have to do it here for now.
        return str(url)


class WishModel(Schema):
    """Wish creation"""

    name: str
    price: Optional[str] = None
    url: Optional[AnyUrl] = None
    description: Optional[str] = None

    @field_validator("url", mode="before")
    @classmethod
    def convert_empty_url_to_none(cls, url: AnyUrl | str, info: ValidationInfo) -> AnyUrl | None:
        """Convert empty string to None to avoid validation error"""
        return url if url else None

    @model_validator(mode="before")
    @classmethod
    def check_whether_name_is_none(cls, data: DjangoGetter) -> Any:
        if not data.name:
            raise PydanticCustomError(
                "none_value_not_allowed",
                "Name can not be null nor empty",
            )
        return data


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
                "Name can not be null nor empty",
            )
        return data


class WishModelUpdateAssignUser(BaseSchema):
    """Wish Update (only assigned_user is changing)"""

    assigned_user: Optional[str] = None


class WishListUserModel(BaseSchema):
    user: str
    wishes: Optional[list[WishListWishModel]] = []


class UserWishDataModel(BaseSchema):
    user: str
    wish: WishListWishModel


class UserDeletedWishDataModel(BaseSchema):
    user: str
    wish_id: UUID4
    assigned_user: Optional[str] = None


class WishListModel(BaseSchema):
    wishlist_id: UUID4
    name: str
    allow_see_assigned: bool
    current_user: str
    is_current_user_admin: bool
    user_wishes: list[WishListUserModel]


class WishListSettingsData(BaseSchema):
    wishlist_name: str
    allow_see_assigned: bool


class WishListUserCreate(BaseSchema):
    """WishListUser based on the Wishlist model"""

    name: str
    is_active: bool = True


class Message(Schema):
    message: str


class ErrorMessage(Schema):
    error: Message


class WebhookPayloadModel(BaseSchema):
    type: str
    currentUser: UUID4
    post_values: Optional[dict] = {}
    object_id: Optional[UUID4] = None

    class Config(Schema.Config):
        alias_generator = to_camel
        populate_by_name = True

    # todo validate if post_values is not None, then objectId should not be None
