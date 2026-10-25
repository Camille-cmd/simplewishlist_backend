from django.contrib import admin

from core.models import Wish, WishAssignment, WishList, WishListUser


class WishAssignmentInline(admin.TabularInline):
    model = WishAssignment
    extra = 0


@admin.register(Wish)
class WishAdmin(admin.ModelAdmin):
    list_display = ("name", "wishlist_user", "assigned_users_display", "deleted")
    inlines = [WishAssignmentInline]

    @admin.display(description="Taken by")
    def assigned_users_display(self, obj):
        return ", ".join(obj.assigned_users.values_list("name", flat=True))


@admin.register(WishAssignment)
class WishAssignmentAdmin(admin.ModelAdmin):
    list_display = ("wish", "user", "assigned_at")


@admin.register(WishList)
class WishListAdmin(admin.ModelAdmin):
    pass


@admin.register(WishListUser)
class WishListUserAdmin(admin.ModelAdmin):
    pass
