from django.shortcuts import get_object_or_404

from api.pydantic_models import WishModelUpdate
from core.models import Wish, WishListUser


def update_wish(current_user: WishListUser, wish_id: int, payload: WishModelUpdate):
    """Update a wish from a wish id"""
    instance = get_object_or_404(Wish, pk=wish_id)

    instance.update(current_user_id=current_user.id, update_data=payload.dict(exclude_unset=True))
