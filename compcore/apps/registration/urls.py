from django.urls import path
from .views import register, register_success, team_create, team_join

urlpatterns = [
    path('<slug:slug>/', register, name='registration_register'),
    path('<slug:slug>/success/', register_success, name='registration_success'),
    path('<slug:slug>/team/create/', team_create, name='team_create'),
    path('<slug:slug>/team/join/', team_join, name='team_join'),
]