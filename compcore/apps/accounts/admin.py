from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "id_document", "date_of_birth", "gym", "phone")
    search_fields = ("user__username", "user__email", "id_document")