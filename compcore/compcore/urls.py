from django.contrib import admin
from django.urls import path, include
from compcore.apps.events import views as event_views

# Alias a dashboard de jueces (mantiene el name 'event_judges')
from compcore.apps.judging.views import dashboard as judges_dashboard
# Vista pública de resultados
from compcore.apps.judging.views import results_event

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),

    # Home
    path("", event_views.home, name="home"),

    # Mantener /events/<slug>/judges/ apuntando al dashboard nuevo (alias compatible)
    path("events/<slug:slug>/judges/", judges_dashboard, name="event_judges"),

    # App Events (NO se toca)
    path("events/", include("compcore.apps.events.urls")),

    # API healthcheck (existente)
    path("api/health/", event_views.health, name="api_health"),

    # Heats públicos (existentes; NO se tocan)
    path("heats/<slug:event_slug>/w<int:order>/", event_views.public_heats, name="public_heats"),
    path("heats/<slug:event_slug>/w<int:order>/h<int:heat_number>/", event_views.heat_detail, name="heat_detail"),

    # Resultados públicos por evento (sin filtros)
    path("results/<slug:event_slug>/", results_event, name="public_results"),

    # Módulo 'judging' con namespace (editor por heat)
    path("judging/", include(("compcore.apps.judging.urls", "judging"), namespace="judging")),

    # >>> NUEVOS ALIAS (no rompen nada existente) <<<
    # Leaderboard: habilita /leaderboard/, /leaderboard/<slug>/ y live
    path("leaderboard/", include("compcore.apps.leaderboard.urls")),

    # Registro: habilita /register/<slug>/ y subrutas
    path("register/", include("compcore.apps.registration.urls")),
]