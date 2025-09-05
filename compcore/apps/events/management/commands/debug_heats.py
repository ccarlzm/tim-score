from django.core.management.base import BaseCommand, CommandError

from compcore.apps.events.models import Event, Workout, Division
from compcore.apps.events.services.heats import (
    participants_for_division,
    rank_participants,
    plan_distribution,
    clear_auto_assignments,
    apply_plan,
)

class Command(BaseCommand):
    help = "Muestra el ranking usado para seedear heats y la propuesta de distribución. Usa --apply para escribir en BD."

    def add_arguments(self, parser):
        parser.add_argument("event_slug", type=str, help="Slug del evento (ej: force-games)")
        parser.add_argument("workout_order", type=int, help="Orden del WOD (ej: 2)")
        parser.add_argument("division_name", type=str, help="Nombre EXACTO de la división (ej: Rx)")
        parser.add_argument("--apply", action="store_true", help="Aplicar la propuesta a la BD")

    def handle(self, *args, **opts):
        event_slug = opts["event_slug"]
        order = opts["workout_order"]
        div_name = opts["division_name"]

        try:
            event = Event.objects.get(slug=event_slug)
        except Event.DoesNotExist:
            raise CommandError(f"Event '{event_slug}' no existe.")

        try:
            workout = Workout.objects.get(event=event, order=order)
        except Workout.DoesNotExist:
            raise CommandError(f"WOD con order={order} para event '{event_slug}' no existe.")

        try:
            division = Division.objects.get(event=event, name=div_name)
        except Division.DoesNotExist:
            raise CommandError(f"Division '{div_name}' no existe en event '{event_slug}'.")

        parts = participants_for_division(event, division)
        ranked, best_last = rank_participants(workout, division, parts)
        plan = plan_distribution(workout, division, ranked, best_last)

        self.stdout.write(self.style.MIGRATE_HEADING(f"{event.name} · W{workout.order} {workout.title}"))
        self.stdout.write(f"División: {division.name} · capacidad/heat: {plan.heat_capacity} · heats: {plan.needed_heats}")
        self.stdout.write(f"Modo: {'líderes → último heat' if plan.assign_best_to_last else 'fallback (WOD1 o single heat)'}\n")

        self.stdout.write(self.style.HTTP_INFO("Top 10 (mejor→peor) por puntos acumulados hasta el WOD anterior:"))
        for i, rp in enumerate(plan.ranked[:10], 1):
            self.stdout.write(f"{i:>2}. {rp.display:30s}  pts_prev={rp.points_prev:.1f}")

        self.stdout.write("\nPropuesta:")
        for hnum in sorted(plan.distribution.keys()):
            labels = ", ".join([rp.display for rp in plan.distribution[hnum]]) or "(vacío)"
            self.stdout.write(f"  Heat {hnum}: {labels}")

        if opts["apply"]:
            clear_auto_assignments(workout, division)
            created = apply_plan(plan)
            self.stdout.write(self.style.SUCCESS(f"\nAplicado. Asignaciones automáticas creadas: {created}"))
        else:
            self.stdout.write("\n(Solo vista previa; usa --apply para escribir a BD.)")