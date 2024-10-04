from django.shortcuts import get_object_or_404

from api.pydantic_models import WishModelUpdate, WishListUserModel, WishListModel
from core.models import Wish, WishListUser, WishList


def do_update_wish(current_user: WishListUser, wish_id: int, payload: WishModelUpdate, exclude_unset: bool = True):
    """
    Update a wish from a wish id

    Args:
        current_user (WishListUser): The current user
        wish_id (int): The wish id
        payload (WishModelUpdate): The payload to update the wish
        exclude_unset (bool): Exclude the None values from the payload (default: True)
    """
    instance = get_object_or_404(Wish, pk=wish_id)

    instance.update(current_user_id=current_user.id, update_data=payload.dict(exclude_unset=exclude_unset))


def get_all_users_wishes(wishlist: WishList, current_user: WishListUser) -> list[WishListUserModel]:
    """Return all the wishes of all the users in the wishlist"""
    users = wishlist.get_active_users()
    users_wishes = []
    for user in users:
        wishes = user.get_user_wishes()
        wish_schema = WishListUserModel(
            user=user.name,
            wishes=wishes,
        )

        if user == current_user:
            # The current user should be the first one
            users_wishes.insert(0, wish_schema)
        else:
            users_wishes.append(wish_schema)

    return users_wishes


def get_wishlist_data(user: WishListUser) -> WishListModel:
    """Get the wishlist users and corresponding wishes"""
    wishlist = user.wishlist
    # For each user, we need to collect their wishes
    users_wishes = get_all_users_wishes(wishlist, user)

    return WishListModel(
        wishlist_id=wishlist.id,
        name=wishlist.wishlist_name,
        allow_see_assigned=wishlist.show_users,
        current_user=user.name,
        is_current_user_admin=user.is_admin,
        user_wishes=users_wishes,
    )
