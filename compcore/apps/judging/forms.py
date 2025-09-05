# compcore/apps/judging/forms.py
from __future__ import annotations

from typing import Optional
from django import forms
from .models import HeatResult, STATUS_CHOICES


# ---------- Utilidades de formateo/parseo de tiempo ----------
def parse_time_to_seconds(value: Optional[str]) -> Optional[int]:
    """
    Acepta '', None, 'mm:ss' o 'hh:mm:ss' y devuelve segundos (int) o None.
    No acepta comas ni puntos como separador.
    """
    if value in (None, ""):
        return None
    value = value.strip()
    parts = value.split(":")
    try:
        if len(parts) == 2:
            mm, ss = parts
            mm, ss = int(mm), int(ss)
            if not (0 <= ss < 60 and mm >= 0):
                raise ValueError
            return mm * 60 + ss
        elif len(parts) == 3:
            hh, mm, ss = parts
            hh, mm, ss = int(hh), int(mm), int(ss)
            if not (0 <= mm < 60 and 0 <= ss < 60 and hh >= 0):
                raise ValueError
            return hh * 3600 + mm * 60 + ss
    except Exception:
        pass
    raise forms.ValidationError("Formato inválido. Use mm:ss o hh:mm:ss (ej. 05:30 o 00:05:30).")


def format_seconds(value: Optional[int]) -> str:
    if value in (None, "", 0):
        return ""
    try:
        value = int(value)
    except Exception:
        return ""
    hh, rem = divmod(value, 3600)
    mm, ss = divmod(rem, 60)
    if hh:
        return f"{hh:02d}:{mm:02d}:{ss:02d}"
    return f"{mm:02d}:{ss:02d}"


# ---------- Form principal para cada fila del formset ----------
class LaneResultForm(forms.ModelForm):
    # Campos de presentación para TIME / TIE-BREAK (strings), mapean a *_seconds
    time_display = forms.CharField(
        required=False,
        label="Tiempo",
        widget=forms.TextInput(attrs={"placeholder": "mm:ss o hh:mm:ss"}),
        help_text="Ej. 05:30 o 00:05:30",
    )
    tiebreak_display = forms.CharField(
        required=False,
        label="Tie-break",
        widget=forms.TextInput(attrs={"placeholder": "mm:ss o hh:mm:ss"}),
    )

    class Meta:
        model = HeatResult
        # No incluimos FKs de participante: team/athlete_entry se definen por la asignación del lane
        fields = [
            "id",            # IMPORTANTE: oculto para formset (edición)
            "lane",          # mostrado solo lectura
            "time_display",  # -> time_seconds
            "reps",
            "weight_kg",
            "penalties",
            "tiebreak_display",  # -> tiebreak_seconds
            "status",
            "judge_name",
            "notes",
        ]
        widgets = {
            "id": forms.HiddenInput(),
            "lane": forms.NumberInput(attrs={"readonly": True, "class": "rf-input rf-input--sm"}),
            "reps": forms.NumberInput(attrs={"min": 0, "step": 1, "class": "rf-input rf-input--sm"}),
            "weight_kg": forms.NumberInput(attrs={"min": 0, "step": "0.5", "class": "rf-input rf-input--sm"}),
            "penalties": forms.NumberInput(attrs={"min": 0, "step": 1, "class": "rf-input rf-input--sm"}),
            "status": forms.Select(choices=STATUS_CHOICES, attrs={"class": "rf-select rf-select--sm"}),
            "judge_name": forms.TextInput(attrs={"class": "rf-input rf-input--sm", "placeholder": "Nombre del juez"}),
            "notes": forms.TextInput(attrs={"class": "rf-input rf-input--sm", "placeholder": "Notas"}),
        }
        labels = {
            "lane": "Lane",
            "reps": "Reps",
            "weight_kg": "Peso (kg)",
            "penalties": "Penal.",
            "status": "Estado",
            "judge_name": "Juez",
            "notes": "Notas",
        }

    # --------- Inicialización: precargar displays y defaults ----------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Precargar string de tiempo y tiebreak desde los segundos guardados
        if self.instance and self.instance.pk:
            self.fields["time_display"].initial = format_seconds(getattr(self.instance, "time_seconds", None))
            self.fields["tiebreak_display"].initial = format_seconds(getattr(self.instance, "tiebreak_seconds", None))

        # Asegurar default para penalties (BD lo marca NOT NULL)
        if self.initial.get("penalties") in (None, "") and (self.instance is None or self.instance.pk is None):
            self.fields["penalties"].initial = 0

        # Mostrar lane como lectura (pero viajará en POST)
        self.fields["lane"].disabled = True

    # --------- Cleans: convertir strings a segundos ----------
    def clean_time_display(self):
        val = self.cleaned_data.get("time_display")
        return parse_time_to_seconds(val)

    def clean_tiebreak_display(self):
        val = self.cleaned_data.get("tiebreak_display")
        return parse_time_to_seconds(val)

    def clean(self):
        cleaned = super().clean()
        # Reglas básicas de coherencia (no forzamos según tipo de WOD aquí):
        # - No permitir status OK con TODO vacío
        # - No permitir DNF/DNS con tiempos/reps/weight
        time_sec = cleaned.get("time_display")
        tie_sec = cleaned.get("tiebreak_display")
        reps = cleaned.get("reps")
        weight = cleaned.get("weight_kg")
        status = cleaned.get("status") or "OK"

        has_score = any(v not in (None, "", 0) for v in [time_sec, reps, weight])
        if status == "OK" and not has_score:
            raise forms.ValidationError("Debe cargar un valor de Tiempo, Reps o Peso (según corresponda) para estado OK.")

        if status in ("DNF", "DNS", "DQ"):
            if any(v not in (None, "", 0) for v in [time_sec, reps, weight, tie_sec]):
                raise forms.ValidationError("Si el estado es DNF/DNS/DQ, deje vacíos Tiempo/Reps/Peso/Tie-break.")

        return cleaned

    # --------- Guardado: mapear displays a los campos reales ----------
    def save(self, commit=True):
        obj: HeatResult = super().save(commit=False)
        obj.time_seconds = self.cleaned_data.get("time_display")
        obj.tiebreak_seconds = self.cleaned_data.get("tiebreak_display")

        # penalties no nulo
        if obj.penalties is None:
            obj.penalties = 0

        if commit:
            obj.save()
        return obj