from django.core.management.base import BaseCommand
from django.utils import timezone

from compcore.apps.events.models import Event, Division, Workout, WorkoutHeat


class Command(BaseCommand):
    help = "Crea datos mínimos de demo para TIM-SCORE"

    def handle(self, *args, **options):
        e, _ = Event.objects.get_or_create(
            slug="force-games",
            defaults=dict(
                name="Force Games",
                location="West Palm Beach, FL",
                description="Demo de evento para TIM-SCORE.",
                start_date=timezone.localdate(),
                end_date=timezone.localdate(),
                status="OPEN",
                registration_open=True,
                registration_deadline=timezone.localdate() + timezone.timedelta(days=30),
            ),
        )
        self.stdout.write(self.style.SUCCESS(f"Evento: {e}"))

        di, _ = Division.objects.get_or_create(event=e, name="RX Masculino", defaults=dict(team_size=1, gender="M"))
        df, _ = Division.objects.get_or_create(event=e, name="RX Femenino", defaults=dict(team_size=1, gender="F"))
        t2, _ = Division.objects.get_or_create(event=e, name="Team 2 Mixto", defaults=dict(team_size=2, gender="MX", capacity=8))
        self.stdout.write(self.style.SUCCESS("Divisiones creadas."))

        w1, _ = Workout.objects.get_or_create(event=e, order=1, defaults=dict(name="Fran-ish", scoring="TIME", is_published=True))
        w2, _ = Workout.objects.get_or_create(event=e, order=2, defaults=dict(name="Max Clean", scoring="LOAD", is_published=True))
        self.stdout.write(self.style.SUCCESS("Workouts creados."))

        for div in (di, df, t2):
            for n in range(1, 2+1):
                WorkoutHeat.objects.get_or_create(workout=w1, division=div, heat_number=n, defaults=dict(is_published=True))
                WorkoutHeat.objects.get_or_create(workout=w2, division=div, heat_number=n, defaults=dict(is_published=True))
        self.stdout.write(self.style.SUCCESS("Heats creados. ¡Listo!"))