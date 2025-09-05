from __future__ import annotations

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
import secrets
import string

from compcore.apps.events.models import Event, Division
from compcore.apps.accounts.models import Profile


def make_join_code(length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class Team(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    division = models.ForeignKey(Division, on_delete=models.CASCADE)
    name = models.CharField(max_length=160)
    captain = models.ForeignKey(User, on_delete=models.PROTECT)
    join_code = models.CharField(max_length=8, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('division', 'name'),)
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.name} · {self.division}"

    def save(self, *args, **kwargs):
        if not self.join_code:
            code = make_join_code()
            while Team.objects.filter(join_code=code).exists():
                code = make_join_code()
            self.join_code = code
        super().save(*args, **kwargs)

    def member_count(self) -> int:
        return AthleteEntry.objects.filter(team=self).count()

    def sex_counts(self) -> tuple[int, int]:
        males = 0
        females = 0
        for entry in AthleteEntry.objects.filter(team=self).select_related('user__profile'):
            sex = getattr(getattr(entry.user, 'profile', None), 'sex', None)
            if sex == 'M':
                males += 1
            elif sex == 'F':
                females += 1
        return males, females


class AthleteEntry(models.Model):
    """Registro de atleta en un event/division.
    Para individuales: team es NULL y division.team_size == 1
    Para equipos: team != NULL y deben respetarse tamaños/cuotas.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    division = models.ForeignKey(Division, on_delete=models.PROTECT)
    team = models.ForeignKey(Team, null=True, blank=True, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (('user', 'division'),)
        ordering = ('-created_at',)

    def __str__(self) -> str:
        return f"{self.user} · {self.division}"

    def clean(self):
        # Coherencia event/division
        if self.division and self.event_id and self.division.event_id != self.event_id:
            raise ValidationError("La división no pertenece a este evento.")

        # Ventana de registro
        if not self.event.is_registration_open:
            raise ValidationError("La inscripción no está abierta para este evento.")

        d = self.division

        # Capacidad general
        if not d.is_unlimited():
            if d.team_size == 1:
                current = AthleteEntry.objects.filter(division=d, team__isnull=True).count()
                if current >= d.capacity:
                    raise ValidationError("No hay cupos disponibles en esta división (individual).")
            else:
                current_teams = Team.objects.filter(division=d).count()
                if self.team is None and current_teams >= d.capacity:
                    raise ValidationError("No hay cupos disponibles para nuevos equipos en esta división.")

        # Reglas de sexo (sólo individuales, si hay cuotas)
        prof = getattr(self.user, 'profile', None)
        sex = getattr(prof, 'sex', None) if prof else None
        if d.team_size == 1 and d.male_quota is not None and d.female_quota is not None:
            if sex not in ('M', 'F'):
                raise ValidationError("Tu perfil no tiene sexo definido. Actualízalo para poder inscribirte en esta división.")
            m = AthleteEntry.objects.filter(division=d, team__isnull=True, user__profile__sex='M').count()
            f = AthleteEntry.objects.filter(division=d, team__isnull=True, user__profile__sex='F').count()
            if sex == 'M' and (m + 1) > d.male_quota:
                raise ValidationError("No hay cupo para hombres en esta división.")
            if sex == 'F' and (f + 1) > d.female_quota:
                raise ValidationError("No hay cupo para mujeres en esta división.")

        # Reglas de equipos
        if d.team_size > 1:
            if self.team is None:
                return  # crear equipo se valida por capacidad de equipos arriba
            if self.team.member_count() >= d.team_size:
                raise ValidationError(f"El equipo ya alcanzó el tamaño máximo ({d.team_size}).")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)