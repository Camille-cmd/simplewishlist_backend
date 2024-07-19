from django.shortcuts import get_object_or_404

from api.pydantic_models import WishModelUpdate, WishListUserModel
from core.models import Wish, WishListUser, WishList


def do_update_wish(current_user: WishListUser, wish_id: int, payload: WishModelUpdate):
    """Update a wish from a wish id"""
    instance = get_object_or_404(Wish, pk=wish_id)

    instance.update(current_user_id=current_user.id, update_data=payload.dict(exclude_unset=True))


def get_all_users_wishes(wishlist: WishList, as_dict: bool = False):
    """Return all the wishes of all the users in the wishlist"""
    users = wishlist.get_active_users()
    users_wishes = []
    for user in users:
        wishes = user.get_user_wishes()
        wish_schema = WishListUserModel(
            user=user.name,
            wishes=wishes,
        )
        users_wishes.append(wish_schema.dict() if as_dict else wish_schema)

    return users_wishes
