from django.http import HttpRequest
from ninja import Router

from api.pydantic_models import (
    ErrorMessage,
    WishlistInitModel,
    WishListSettingsData,
    WishListUserCreate,
)
from core.models import WishList, WishListUser
from core.pydantic_models import WishListUserFromModel

router = Router()


# WISHLIST
@router.get("/wishlist/settings", response={200: WishListSettingsData}, by_alias=True)
def get_wishlist_settings(request: HttpRequest):
    """
    Get the wishlist settings for the current user.

    Args:
        request (HttpRequest): The HTTP request object containing the current user.

    Returns:
        dict: A dictionary containing the wishlist settings.
    """
    current_user = request.auth

    wishlist = current_user.wishlist

    return WishListSettingsData(
        wishlist_name=wishlist.wishlist_name,
        allow_see_assigned=wishlist.show_users,
    )


@router.put("/wishlist", response={200: list[WishListUserFromModel]}, auth=None, by_alias=True)
def create_wishlist(request: HttpRequest, payload: WishlistInitModel):
    """
    Create a new wishlist.

    Args:
        request (HttpRequest): The HTTP request object without authentication required.
        payload (WishlistInitModel): The data required to create a new wishlist.

    Returns:
        list: The list of users created for the wishlist.
        An error message if the payload is invalid.
    """

    # Create the wishlist
    wishlist = WishList.objects.create(
        wishlist_name=payload.wishlist_name,
        show_users=payload.allow_see_assigned,
    )

    # Add users
    created_users = []
    # The admin is one of the users
    wishlist_admin = WishListUser.objects.create(name=payload.wishlist_admin_name, wishlist=wishlist, is_admin=True)
    # The others
    created_users.append(wishlist_admin)
    if other_users_names := payload.other_users_names:
        for other_user_name in other_users_names:
            created_user = WishListUser.objects.create(
                name=other_user_name,
                wishlist=wishlist,
            )
            created_users.append(created_user)

    return created_users


@router.post("/wishlist", response={200: WishListSettingsData, 401: ErrorMessage}, by_alias=True)
def update_wishlist(request: HttpRequest, payload: WishListSettingsData):
    """
    Update the wishlist settings.

    Args:
        request (HttpRequest): The HTTP request object containing the current user.
        payload (WishListSettingsData): The data required to update the wishlist settings.

    Returns:
        dict: A dictionary containing the updated wishlist settings if successful.
        ErrorMessage: An error message if the user is not an admin.
    """

    current_user = request.auth
    if not current_user.is_admin:
        return 401, {"error": {"message": "Only the admin can update the wishlist"}}

    wishlist = current_user.wishlist

    # Update the wishlist
    wishlist.wishlist_name = payload.wishlist_name
    wishlist.show_users = payload.allow_see_assigned
    wishlist.save()

    return WishListSettingsData(
        wishlist_name=wishlist.wishlist_name,
        allow_see_assigned=wishlist.show_users,
    )


@router.get("/wishlist/users", response={200: list[WishListUserFromModel]}, by_alias=True)
def get_wishlist_users(request: HttpRequest):
    """
     Get all the users of the wishlist for the current user.

    Args:
        request (HttpRequest): The HTTP request object containing the current user.

    Returns:
        list: a list of users in the wishlist including the current user.
    """
    current_user = request.auth
    wishlist = current_user.wishlist

    users = wishlist.get_users()
    return 200, users


@router.post(
    "/wishlist/users/{user_id}/deactivate",
    response={200: WishListUserFromModel, 401: ErrorMessage, 404: ErrorMessage},
    by_alias=True,
)
def deactivate_user(request: HttpRequest, user_id: str):
    """
    Deactivate a user from the wishlist.

    Args:
        request (HttpRequest): The HTTP request object containing the current user.
        user_id (str): The ID of the user to deactivate.

    Returns:
        dict: A dictionary containing the deactivated user's information if successful.
        ErrorMessage: An error message if the user is not an admin, if the user is an admin, or if the user is not found.

    Raises:
        SimpleWishlistValidationError: If there is a validation error during the deactivation of the user.
    """
    current_user = request.auth
    if not current_user.is_admin:
        return 401, {"error": {"message": "Only the admin can deactivate a user"}}

    wishlist = current_user.wishlist

    try:
        user = wishlist.wishlist_users.get(id=user_id)
        if user.is_admin:
            return 401, {"error": {"message": "The admin can not be deactivated"}}
        user.is_active = False
        user.save()
        return 200, user
    except WishListUser.DoesNotExist:
        return 404, {"error": {"message": "User not found"}}


@router.post(
    "/wishlist/users/{user_id}/activate",
    response={200: WishListUserFromModel, 401: ErrorMessage, 404: ErrorMessage},
    by_alias=True,
)
def activate_user(request: HttpRequest, user_id: str):
    """
    Activate a user from the wishlist.

    Args:
        request (HttpRequest): The HTTP request object containing the current user.
        user_id (str): The ID of the user to activate.

    Returns:
        dict: A dictionary containing the activated user's information if successful.
        ErrorMessage: An error message if the user is not an admin or if the user is not found.

    Raises:
        SimpleWishlistValidationError: If there is a validation error during the activation of the user.
    """
    current_user = request.auth
    if not current_user.is_admin:
        return 401, {"error": {"message": "Only the admin can activate a user"}}

    wishlist = current_user.wishlist

    try:
        user = wishlist.wishlist_users.get(id=user_id)
        user.is_active = True
        user.save()
        return 200, user
    except WishListUser.DoesNotExist:
        return 404, {"error": {"message": "User not found"}}


@router.put(
    "/wishlist/users",
    response={201: WishListUserFromModel, 401: ErrorMessage, 400: ErrorMessage},
    by_alias=True,
)
def add_new_user_to_wishlist(request: HttpRequest, payload: WishListUserCreate):
    """
    Add a new user to the wishlist.

    Args:
        request (HttpRequest): The HTTP request object containing the current user.
        payload (WishListUserCreate): The data required to create a new wishlist user.

    Returns:
        dict: A dictionary containing the created user's information if successful.
        ErrorMessage: An error message if the user is not an admin or if there is another error.

    Raises:
        SimpleWishlistValidationError: If there is a validation error during the creation of the user.
    """
    current_user = request.auth
    if not current_user.is_admin:
        return 401, {"error": {"message": "Only the admin can add a user"}}

    if payload.name in current_user.wishlist.get_users().values_list("name", flat=True):
        return 400, {"error": {"message": "User already exists in the wishlist"}}

    wishlist = current_user.wishlist
    created_user = WishListUser.objects.create(**payload.dict(), wishlist=wishlist)
    return 201, created_user


@router.post(
    "/wishlist/users/{user_id}",
    response={200: WishListUserFromModel, 401: ErrorMessage, 400: ErrorMessage, 404: ErrorMessage},
    by_alias=True,
)
def update_user_in_wishlist(request: HttpRequest, user_id: str, payload: WishListUserCreate):
    """
    Update a user in the wishlist.

    Args:
        request (HttpRequest): The HTTP request object containing the current user.
        user_id (str): The ID of the user to update.
        payload (WishListUserCreate): The data required to update the user.

    Returns:
        User: If the user is successfully updated.
        ErrorMessage: An error message if the user is not an admin or if there is another error.

    Raises:
        SimpleWishlistValidationError: If there is a validation error during the update of the user.
    """
    current_user = request.auth
    if not current_user.is_admin:
        return 401, {"error": {"message": "Only the admin can update a user"}}

    # Check if the user exists in the wishlist but exclude the user being updated, as the user can keep the same name
    if payload.name in current_user.wishlist.get_users(exclude_users_ids=[user_id]).values_list("name", flat=True):
        return 400, {"error": {"message": "User already exists in the wishlist"}}

    try:
        user = WishListUser.objects.get(id=user_id)
        user.name = payload.name
        user.save()
        return 200, user
    except WishListUser.DoesNotExist:
        return 404, {"error": {"message": "User not found"}}
