from django.shortcuts import get_object_or_404

from api.pydantic_models import WishModelUpdate, WishListUserModel, WishListModel
from core.models import Wish, WishListUser, WishList


def do_update_wish(
    current_user: WishListUser, wish_id: int, payload: WishModelUpdate, exclude_unset: bool = True
) -> Wish:
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

    return instance


def get_all_users_wishes(wishlist: WishList, current_user: WishListUser) -> list[WishListUserModel]:
    """Return all the wishes of all the users in the wishlist"""
    from api.pydantic_models import WishListWishModel

    users = wishlist.get_active_users()
    users_wishes = []
    for user in users:
        # Get all wishes for this user
        wishes_queryset = user.wishes.all()

        # Filter out suggested wishes if the current user is viewing their own wishes
        if user == current_user:
            wishes_queryset = wishes_queryset.exclude(suggested_by__isnull=False)

        # Convert to pydantic models
        wishes = []
        for wish in wishes_queryset:
            wishes.append(
                WishListWishModel(
                    name=wish.name,
                    price=wish.price or None,
                    description=wish.description or None,
                    url=wish.url or None,
                    id=wish.id,
                    assigned_user=wish.assigned_user.name if wish.assigned_user else None,
                    deleted=wish.deleted,
                    suggested_by=wish.suggested_by.name if wish.suggested_by else None,
                )
            )

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
        surprise_mode_enabled=wishlist.is_surprise_mode_enabled,
        allow_see_assigned=wishlist.show_users,
        current_user=user.name,
        user_wishes=users_wishes,
    )
