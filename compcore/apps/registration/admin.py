from __future__ import annotations

from django.contrib import admin

from .models import Team, AthleteEntry


class TeamMembersInline(admin.TabularInline):
    model = AthleteEntry
    extra = 0
    fields = ("user", "created_at")
    readonly_fields = ("user", "created_at")
    can_delete = False
    show_change_link = True


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "event",
        "division",
        "captain",
        "members_count",
        "male_count",
        "female_count",
        "join_code",
        "created_at",
    )
    list_filter = ("event", "division")
    search_fields = ("name", "join_code", "captain__username", "captain__email")
    raw_id_fields = ("event", "division", "captain")
    inlines = [TeamMembersInline]

    def members_count(self, obj: Team) -> int:
        return obj.member_count()
    members_count.short_description = "Miembros"

    def male_count(self, obj: Team) -> int:
        m, f = obj.sex_counts()
        return m
    male_count.short_description = "Hombres"

    def female_count(self, obj: Team) -> int:
        m, f = obj.sex_counts()
        return f
    female_count.short_description = "Mujeres"


@admin.register(AthleteEntry)
class AthleteEntryAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "division", "team", "user_sex", "created_at")
    list_filter = ("event", "division", "team")
    search_fields = ("user__username", "user__email", "team__name")
    raw_id_fields = ("user", "event", "division", "team")

    def user_sex(self, obj: AthleteEntry) -> str | None:
        prof = getattr(obj.user, "profile", None)
        return getattr(prof, "sex", None)
    user_sex.short_description = "Sexo"