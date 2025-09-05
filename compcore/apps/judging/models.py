# compcore/apps/judging/models.py
from __future__ import annotations

from django.db import models
from django.utils import timezone

STATUS_CHOICES = (
    ("OK", "OK"),
    ("DNF", "DNF"),  # Did Not Finish
    ("DNS", "DNS"),  # Did Not Start
    ("DQ", "DQ"),    # Disqualified
)

class HeatResult(models.Model):
    """
    Resultado cargado por jueces para un lane de un heat específico.
    Se fuerza unicidad por (heat, lane) para evitar duplicados.
    """
    heat = models.ForeignKey(
        "events.WorkoutHeat",
        on_delete=models.CASCADE,
        related_name="results",
    )
    # Guardamos referencia opcional del participante para conveniencia:
    team = models.ForeignKey(
        "registration.Team",
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name="heat_results"
    )
    athlete_entry = models.ForeignKey(
        "registration.AthleteEntry",
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name="heat_results"
    )

    lane = models.PositiveIntegerField()

    # Puntuación
    time_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Tiempo total en segundos.")
    reps = models.PositiveIntegerField(null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    penalties = models.IntegerField(default=0)
    tiebreak_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="Tie-break en segundos.")
    status = models.CharField(max_length=3, choices=STATUS_CHOICES, default="OK")

    judge_name = models.CharField(max_length=120, blank=True, default="")
    notes = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = (("heat", "lane"),)
        ordering = ("heat_id", "lane")

    def __str__(self) -> str:
        who = self.team or self.athlete_entry
        return f"{self.heat} · Lane {self.lane} · {who or '—'}"