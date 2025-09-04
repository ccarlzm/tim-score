# compcore/apps/judging/management/commands/seed_w1h4_results.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Model

from compcore.apps.events.models import Event, Workout, WorkoutHeat, HeatAssignment
from compcore.apps.judging.models import HeatResult


class Command(BaseCommand):
    help = "Inyecta resultados de prueba para W1 Heat #4 (division id=2) en el evento 'force-games'"

    def add_arguments(self, parser):
        parser.add_argument("--event-slug", default="force-games", help="Slug del evento (default: force-games)")
        parser.add_argument("--workout-order", type=int, default=1, help="Orden del workout (default: 1 = W1)")
        parser.add_argument("--division-id", type=int, default=2, help="ID de la división (default: 2)")
        parser.add_argument("--heat-number", type=int, default=4, help="Número de Heat (default: 4)")

    def _field_names(self, model: Model):
        """Devuelve el set de nombres de campos reales del modelo (incluye FKs)."""
        return {f.name for f in model._meta.get_fields()}

    @transaction.atomic
    def handle(self, *args, **opts):
        event_slug = opts["event_slug"]
        w_order = opts["workout_order"]
        division_id = opts["division_id"]
        heat_number = opts["heat_number"]

        self.stdout.write(self.style.WARNING(
            f"Buscando Event='{event_slug}', Workout order={w_order}, Division id={division_id}, Heat #{heat_number}"
        ))

        event = Event.objects.filter(slug=event_slug).first()
        if not event:
            self.stderr.write(self.style.ERROR(f"No se encontró el evento con slug='{event_slug}'"))
            return

        workout = Workout.objects.filter(event=event, order=w_order).first()
        if not workout:
            self.stderr.write(self.style.ERROR(f"No se encontró Workout order={w_order} para el evento '{event_slug}'"))
            return

        heat = WorkoutHeat.objects.filter(
            workout=workout, division_id=division_id, heat_number=heat_number
        ).first()

        if not heat:
            # Fallback por si el division_id no coincide; usar cualquier heat #4 del W1
            heat = WorkoutHeat.objects.filter(workout=workout, heat_number=heat_number).first()
            if not heat:
                self.stderr.write(self.style.ERROR("No se encontró el Heat especificado."))
                return
            self.stdout.write(self.style.WARNING(
                f"Usando heat id={heat.id} con division_id={heat.division_id} (no coincidió division_id={division_id})"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"OK => Event={event.slug}, Workout=W{workout.order}, DivisionID={heat.division_id}, "
            f"Heat #{heat.heat_number} (id={heat.id})"
        ))

        # Introspección de campos disponibles en HeatResult
        fields = self._field_names(HeatResult)
        # ¿El modelo exige enlazar a la asignación?
        has_assignment = "assignment" in fields or "heat_assignment" in fields

        # Semilla (asumimos W1 = For Time). Ajusta si tu W1 es AMRAP/LOAD.
        samples = [
            # lane, time_seconds, tiebreak_seconds, reps, weight, notes
            (1, 354,  90, None, None, "W1 TIME demo: 5:54 / TB 1:30"),
            (2, 372,  95, None, None, "W1 TIME demo: 6:12 / TB 1:35"),
            (3, 401, 110, None, None, "W1 TIME demo: 6:41 / TB 1:50"),
            (4, 415, 120, None, None, "W1 TIME demo: 6:55 / TB 2:00"),
            (5, 442, 135, None, None, "W1 TIME demo: 7:22 / TB 2:15"),
        ]

        created, updated = 0, 0
        for lane, tsec, tbsec, reps, weight, notes in samples:
            # Asegurar la asignación del lane (coherencia con el flujo normal)
            assignment, _ = HeatAssignment.objects.get_or_create(
                heat=heat, lane=lane, defaults={"is_manual": True}
            )

            # Construir filtros para identificar unívocamente el HeatResult
            # Preferimos (assignment) si el modelo lo tiene; si no, usamos (heat, lane).
            lookup = {}
            if "assignment" in fields:
                lookup["assignment"] = assignment
            elif "heat_assignment" in fields:
                lookup["heat_assignment"] = assignment
            else:
                lookup["heat"] = heat
                if "lane" in fields:
                    lookup["lane"] = lane

            # Defaults solo con campos que existen realmente
            defaults = {}
            if "time_seconds" in fields:      defaults["time_seconds"] = tsec
            if "tiebreak_seconds" in fields:  defaults["tiebreak_seconds"] = tbsec
            if "reps" in fields:              defaults["reps"] = reps
            if "weight" in fields:            defaults["weight"] = weight
            if "is_dnf" in fields:            defaults["is_dnf"] = False
            if "is_dns" in fields:            defaults["is_dns"] = False
            if "notes" in fields:             defaults["notes"] = notes

            # NO establecer 'status' si el campo no existe (evita errores de choices)
            if "status" in fields:
                # Si tu modelo define choices para status, usa uno válido; si no, omite.
                # Intentamos valor neutro si existe:
                try:
                    defaults["status"] = getattr(HeatResult, "STATUS_OK", "OK")
                except Exception:
                    defaults["status"] = "OK"

            obj, was_created = HeatResult.objects.update_or_create(
                **lookup, defaults=defaults
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f"Resultados cargados: creados={created}, actualizados={updated}."
        ))
        self.stdout.write(self.style.HTTP_INFO(
            f"Ahora revisa /results/{event.slug}/ (y, si publicas el heat, /heats/{event.slug}/w{workout.order}/h{heat.heat_number}/)"
        ))