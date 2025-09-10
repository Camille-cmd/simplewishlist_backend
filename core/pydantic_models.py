import uuid

from ninja import ModelSchema, Schema
from pydantic.alias_generators import to_camel

from core.models import WishListUser


class WishListUserFromModel(ModelSchema):
    class Meta:
        model = WishListUser
        fields = ["id", "name", "is_admin", "is_active"]

    wishlist_id: uuid.UUID

    class Config(Schema.Config):
        populate_by_name = True
        alias_generator = to_camel

    @staticmethod
    def resolve_wishlist_id(obj):
        return obj.wishlist_id


class WishListSettingHandleUsersData(Schema):
    wishlist_name: str
    wishlist_id: uuid.UUID
    users: list[WishListUserFromModel]

    class Config(Schema.Config):
        populate_by_name = True
        alias_generator = to_camel
