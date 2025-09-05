from django.urls import path
from . import views

# Namespace del app para usar 'judging:...' en {% url %}
app_name = "judging"

urlpatterns = [
    # Editor por heat (incluye event_slug porque la vista lo necesita)
    path(
        "<slug:event_slug>/w<int:workout_order>/d<int:division_id>/heat/<int:heat_number>/",
        views.heat_results_edit,
        name="judging_heat_results",
    ),
]