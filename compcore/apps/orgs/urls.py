# compcore/apps/orgs/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="orgs_dashboard"),
]