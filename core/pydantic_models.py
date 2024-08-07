from ninja import ModelSchema, Schema
from pydantic.alias_generators import to_camel

from core.models import WishListUser


class WishListUserFromModel(ModelSchema):
    class Meta:
        model = WishListUser
        fields = ["id", "name", "is_admin", "is_active"]

    class Config(Schema.Config):
        populate_by_name = True
        alias_generator = to_camel
