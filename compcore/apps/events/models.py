from __future__ import annotations

from django.db import models
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Max


class Event(models.Model):
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("OPEN", "Open"),
        ("CLOSED", "Closed"),
        ("FINISHED", "Finished"),
    )

    name = models.CharField(max_length=160)
    slug = models.SlugField(unique=True)
    location = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)

    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    registration_open = models.BooleanField(default=False)
    registration_deadline = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="DRAFT")

    lanes_default = models.PositiveIntegerField(
        default=8,
        help_text="Carriles por defecto si la división no define capacidad.",
    )
    allow_self_signup = models.BooleanField(
        default=False,
        help_text="Si está activo, se muestra el enlace de 'Crear cuenta' para atletas.",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-start_date", "name")

    def __str__(self) -> str:
        return self.name

    def clean(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError("end_date no puede ser anterior a start_date")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_registration_open(self) -> bool:
        if not self.registration_open:
            return False
        if self.registration_deadline and timezone.localdate() > self.registration_deadline:
            return False
        return True


class Division(models.Model):
    GENDER_CHOICES = (
        ("ANY", "Mixto / Cualquiera"),
        ("M", "Masculino"),
        ("F", "Femenino"),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    slug = models.SlugField(help_text="Slug único dentro del evento.")
    gender = models.CharField(max_length=8, choices=GENDER_CHOICES, default="ANY")
    team_size = models.PositiveIntegerField(default=1, help_text="1 = Individual")
    heat_capacity = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Si está vacío, usa lanes_default del evento.",
    )
    male_quota = models.PositiveIntegerField(null=True, blank=True)
    female_quota = models.PositiveIntegerField(null=True, blank=True)
    min_age = models.PositiveIntegerField(null=True, blank=True)
    max_age = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        unique_together = (("event", "slug"),)
        ordering = ("name", "id")

    def __str__(self) -> str:
        return f"{self.event.name} · {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Workout(models.Model):
    SCORING_CHOICES = (
        ("TIME", "Time"),
        ("REPS", "Reps"),
        ("WEIGHT", "Weight"),
        ("POINTS", "Points"),
    )

    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(help_text="Orden del WOD dentro del evento (1..N).")
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    scoring = models.CharField(max_length=16, choices=SCORING_CHOICES, default="TIME")
    is_published = models.BooleanField(default=False)

    class Meta:
        unique_together = (("event", "order"),)
        ordering = ("event", "order")

    def __str__(self) -> str:
        return f"{self.event.name} · W{self.order} · {self.name}"


class WorkoutHeat(models.Model):
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE)
    division = models.ForeignKey(Division, on_delete=models.CASCADE)
    # 🔑 heat_number GLOBAL por workout (no por división)
    heat_number = models.PositiveIntegerField()
    start_time = models.DateTimeField(null=True, blank=True)
    lane_count = models.PositiveIntegerField(default=8)
    is_published = models.BooleanField(default=False)

    class Meta:
        constraints = [
            # Un número de heat no se puede repetir en el MISMO workout
            models.UniqueConstraint(fields=("workout", "heat_number"), name="uniq_workout_heatnumber"),
        ]
        ordering = ("workout", "heat_number")

    def __str__(self) -> str:
        return f"{self.workout} · {self.division.name} · Heat {self.heat_number}"

    def save(self, *args, **kwargs):
        # Asignación automática: numeración global por workout
        if not self.heat_number:
            max_num = WorkoutHeat.objects.filter(workout=self.workout).aggregate(m=Max("heat_number"))["m"] or 0
            self.heat_number = max_num + 1
        super().save(*args, **kwargs)


class HeatAssignment(models.Model):
    heat = models.ForeignKey(WorkoutHeat, on_delete=models.CASCADE, related_name="assignments")
    athlete_entry = models.ForeignKey("registration.AthleteEntry", on_delete=models.CASCADE, null=True, blank=True)
    team = models.ForeignKey("registration.Team", on_delete=models.CASCADE, null=True, blank=True)
    lane = models.PositiveIntegerField(null=True, blank=True)
    is_manual = models.BooleanField(default=False, help_text="Marcado manualmente por admin.")
    locked = models.BooleanField(default=False, help_text="No mover en re-siembra.")
    # 🔧 Importante: la BD ya tiene esta columna como NOT NULL
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=~(models.Q(athlete_entry__isnull=False) & models.Q(team__isnull=False)),
                name="only_one_entrant",
            ),
        ]
        ordering = ("heat", "lane")

    def __str__(self) -> str:
        who = self.team or self.athlete_entry
        return f"{self.heat} · Lane {self.lane or '-'} · {who}"