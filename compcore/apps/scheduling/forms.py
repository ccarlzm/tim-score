from __future__ import annotations
from django import forms
from compcore.apps.events.models import Event

class SchedulingParamsForm(forms.Form):
    event = forms.ModelChoiceField(queryset=Event.objects.all().order_by("-start_date", "name"))

    # Ventana operativa
    start_time = forms.TimeField(label="Inicio del día", initial="08:00")
    end_time = forms.TimeField(label="Fin del día", initial="18:00")

    # Pausa de almuerzo (opcional)
    lunch_start = forms.TimeField(label="Lunch inicio", required=False)
    lunch_end = forms.TimeField(label="Lunch fin", required=False)

    # Buffers por heat
    briefing_min = forms.IntegerField(label="Briefing (min)", min_value=0, initial=2)
    reset_min = forms.IntegerField(label="Reset (min)", min_value=0, initial=5)
    validation_min = forms.IntegerField(label="Validación (min)", min_value=0, initial=1)

    # Call/Descansos
    call_offset_min = forms.IntegerField(label="Call antes del start (min)", min_value=0, initial=5)
    rest_base_min = forms.IntegerField(label="Descanso base por división (min)", min_value=0, initial=30)
    rest_factor = forms.FloatField(label="Factor×cap para descanso", min_value=0.0, initial=2.0)

    # Colchón al final de cada W
    block_cushion_min = forms.IntegerField(label="Colchón post-bloque (min)", min_value=0, initial=5)