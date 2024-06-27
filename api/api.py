from ninja import Router
from django.http import HttpRequest
from django.shortcuts import get_object_or_404

from api.exceptions import SimpleWishlistValidationError
from api.pydantic_models import WishListLModel, WishListUserModel, WishlistInitModel, WishModel, WishModelUpdate, \
    ErrorMessage
from core.models import WishListUser, WishList, Wish

router = Router()


@router.get("/wishlist", response={200: WishListLModel})
def get_wishlist(request: HttpRequest):
    """Get the wishlist users and corresponding wishes"""

    current_user = request.auth
    
    wishlist = current_user.wishlist
    users = wishlist.wishlist_users.all()

    # For each user, we need to collect the wishes they made and the wishes they took for others
    users_wishes = []
    for user in users:
        # Unassigned wishes
        wishes = user.get_user_wishes(already_assigned=False)
        # Wishes with a user assigned
        wishes_already_assigned = user.get_user_wishes(already_assigned=True)

        users_wishes.append(
            WishListUserModel(
                user=user.name,
                wishes=wishes,
                assignedWishes=wishes_already_assigned,
            )
        )

    return WishListLModel(
        name=wishlist.wishlist_name,
        allowSeeAssigned=wishlist.show_users,
        currentUser=current_user.name,
        isCurrentUserAdmin=current_user.is_admin,
        userWishes=users_wishes,
    )


@router.put("/wishlist", response={200: dict}, auth=None)
def create_wishlist(request: HttpRequest, payload: WishlistInitModel):
    """Create the wishlist with initial data"""

    # Create the wishlist 
    wishlist = WishList.objects.create(
        wishlist_name=payload.wishlist_name,
        show_users=payload.allow_see_assigned,
    )

    # Add users
    created_users = {}
    # The admin is one of the users 
    wishlist_admin = WishListUser.objects.create(
        name=payload.wishlist_admin_name, wishlist=wishlist, is_admin=True
    )
    # The others 
    created_users.update({wishlist_admin.name: wishlist_admin.id})
    if other_users_names := payload.other_users_names:
        for other_user_name in other_users_names:
            created_user = WishListUser.objects.create(
                name=other_user_name,
                wishlist=wishlist,
            )
            created_users.update({created_user.name: created_user.id})

    return created_users


# WISH
@router.put("/wish", response={201: dict})
def create_wish(request: HttpRequest, payload: WishModel):
    current_user = request.auth
    # Add the wishlist user
    wish_data = payload.dict()
    wish_data.update({"wishlist_user": current_user})

    created_wish = Wish.objects.create(**wish_data)

    return {"wish": created_wish.id}


@router.post("/wish/{wish_id}", response={201: dict, 400: ErrorMessage, 404: str})
def update_wish(request: HttpRequest, wish_id: str, payload: WishModelUpdate):
    instance = get_object_or_404(Wish, pk=wish_id)

    current_user = request.auth

    try:
        instance.update(current_user_id=current_user.id, update_data=payload.dict(exclude_unset=True))
        return 201, {"wish": instance.id}
    except SimpleWishlistValidationError as e:
        return 400, {"error": {"message": str(e)}}


@router.delete("/wish/{wish_id}", response={200: None, 401: ErrorMessage, 404: str})
def delete_wish(request: HttpRequest, wish_id: str):
    instance = get_object_or_404(Wish, pk=wish_id)

    current_user = request.auth

    # Only the owner of a wish can delete it
    if instance.wishlist_user.id != current_user.id:
        error = {"message": "Only the owner of the wish can delete it."}
        return 401, {"error": error}
    else:
        instance.delete()
