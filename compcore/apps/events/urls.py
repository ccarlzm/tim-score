from django.urls import path
from . import views

urlpatterns = [
    path("", views.event_list, name="events_list"),
    path("<slug:slug>/leaderboard/", views.event_leaderboard, name="event_leaderboard"),
    path("<slug:slug>/judges/", views.event_judges, name="event_judges"),
    path("<slug:slug>/", views.event_detail, name="event_detail"),
]