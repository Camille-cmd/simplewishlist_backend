from uuid import UUID

from django.shortcuts import get_object_or_404
from ninja import NinjaAPI
from ninja.security import HttpBearer

from api.api import router as api_router
from core.models import WishListUser


class AuthBearer(HttpBearer):
    def authenticate(self, request, token):
        try:
            return get_object_or_404(WishListUser, id=UUID(token))
        except ValueError:
            # ValueError if the token is not uuid
            return None


api = NinjaAPI(auth=AuthBearer())


api.add_router("/v1/", api_router)
