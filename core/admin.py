from django.contrib import admin

from core.models import Wish, WishList, WishListUser


@admin.register(Wish)
class WishAdmin(admin.ModelAdmin):
    pass


@admin.register(WishList)
class WishListAdmin(admin.ModelAdmin):
    pass


@admin.register(WishListUser)
class WishListUserAdmin(admin.ModelAdmin):
    pass
