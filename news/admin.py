from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    ApprovedArticleDelivery,
    Article,
    Newsletter,
    Publisher,
    User,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Extend Django user administration with the newsroom role field."""

    fieldsets = UserAdmin.fieldsets + (
        ("News role", {"fields": ("role",)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ("News role", {"fields": ("role",)}),
    )
    list_display = ("username", "email", "role", "is_staff")


admin.site.register(Publisher)
admin.site.register(Article)
admin.site.register(Newsletter)
admin.site.register(ApprovedArticleDelivery)
