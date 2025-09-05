from django.urls import path
from . import views

urlpatterns = [
    # índice del leaderboard
    path("", views.leaderboard_index, name="leaderboard_index"),

    # live por workout (se usa en los links "ver live")
    path("live/<slug:event_slug>/w<int:order>/", views.leaderboard_live_workout, name="leaderboard_live_workout"),

    # leaderboard por evento (la vista principal que pediste)
    path("<slug:slug>/", views.event_leaderboard, name="event_leaderboard"),
]
