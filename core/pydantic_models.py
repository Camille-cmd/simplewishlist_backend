from ninja import ModelSchema

from core.models import WishListUser


class WishListUserFromModel(ModelSchema):
    class Meta:
        model = WishListUser
        fields = ["id", "name", "is_admin", "is_active"]
