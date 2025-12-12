from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, Company, Job, Application, ApplicationHistory


# -------------------------
# USER ADMIN
# -------------------------

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("id", "username", "email", "role", "is_staff", "is_active")
    list_filter = ("role", "is_staff", "is_superuser", "is_active")
    search_fields = ("username", "email")

    fieldsets = UserAdmin.fieldsets + (
        ("Role", {"fields": ("role",)}),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ("Role", {"fields": ("role",)}),
    )


# -------------------------
# ATS MODELS ADMIN
# -------------------------

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "company", "status")
    list_filter = ("status", "company")
    search_fields = ("title",)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("id", "candidate", "job", "stage", "created_at")
    list_filter = ("stage", "job")
    search_fields = ("candidate__username", "job__title")


@admin.register(ApplicationHistory)
class ApplicationHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "application",
        "from_stage",
        "to_stage",
        "changed_by",
        "changed_at"
    )
    list_filter = ("from_stage", "to_stage")
