from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/wishlist/<uuid:wishlist_user>/", consumers.WishlistConsumer.as_asgi()),
]
