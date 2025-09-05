from __future__ import annotations

import random
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from django.contrib.auth import get_user_model

from compcore.apps.events.models import Event, Division, Workout, WorkoutHeat, HeatAssignment

# Modelos opcionales
Team = None
AthleteEntry = None
ScoreSubmission = None

try:
    from compcore.apps.registration.models import Team as _Team, AthleteEntry as _AthleteEntry
    Team = _Team
    AthleteEntry = _AthleteEntry
except Exception:
    pass

try:
    from compcore.apps.leaderboard.models import ScoreSubmission as _ScoreSubmission
    ScoreSubmission = _ScoreSubmission
except Exception:
    pass


def has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def set_if_has(d: dict, model, **kwargs):
    for k, v in kwargs.items():
        if has_field(model, k) and v is not None:
            d[k] = v
    return d


def ensure_demo_user(username: str, email: str):
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=username, defaults={"email": email})
    if not user.has_usable_password():
        user.set_password("Pass1234!")
        user.save()
    return user


class Command(BaseCommand):
    help = "Crea un evento DEMO con divisiones, workouts, heats y atletas (con usuario si aplica), respetando la validación de HeatAssignment."

    def add_arguments(self, parser):
        parser.add_argument("--event", type=str, default="Force Games V3")
        parser.add_argument("--slug", type=str, default="")
        parser.add_argument("--heats-per-division", type=int, default=3)
        parser.add_argument("--lanes", type=int, default=8)
        parser.add_argument("--workouts", type=int, default=3)
        parser.add_argument("--teams-per-division", type=int, default=18)
        parser.add_argument("--seed-scores", action="store_true")

    @transaction.atomic
    def handle(self, *args, **opts):
        name: str = opts["event"]
        slug: str = opts["slug"] or slugify(name)
        heats_per_div: int = opts["heats_per_division"]
        lanes: int = opts["lanes"]
        workouts_count: int = opts["workouts"]
        teams_per_div: int = opts["teams_per_division"]
        seed_scores: bool = bool(opts["seed_scores"])

        # 1) Evento
        event_defaults = {"name": name}
        set_if_has(event_defaults, Event, location="Demo Arena", is_public=True)

        if Event.objects.filter(slug=slug).exists():
            raise CommandError(f"Ya existe un evento con slug='{slug}'")

        event = Event.objects.create(slug=slug, **event_defaults)
        self.stdout.write(self.style.SUCCESS(f"✓ Evento creado: {slug}"))

        # 2) Divisiones
        divisions = []
        for div_name, gender in [("RX Masculino", "M"), ("RX Femenino", "F")]:
            div_kwargs = {"event": event}
            if has_field(Division, "name"):
                div_kwargs["name"] = div_name
            set_if_has(div_kwargs, Division, gender=gender)
            divisions.append(Division.objects.create(**div_kwargs))
        self.stdout.write(self.style.SUCCESS("✓ Divisiones creadas"))

        # 3) Workouts (solo con campos seguros)
        wods = []
        for i in range(1, workouts_count + 1):
            w_kwargs = {"event": event}
            if has_field(Workout, "order"):
                w_kwargs["order"] = i
            set_if_has(w_kwargs, Workout, description=f"WOD {i} demo", cap_time_seconds=12 * 60)
            wods.append(Workout.objects.create(**w_kwargs))
        self.stdout.write(self.style.SUCCESS("✓ Workouts creados"))

        # 4) Roster por división (guardamos tuplas (team, entry) por índice)
        rosters: dict[int, list[tuple[Optional[object], Optional[object]]]] = {d.id: [] for d in divisions}
        if Team and AthleteEntry:
            # Creamos tanto Team como AthleteEntry, pero en la ASIGNACIÓN usaremos SOLO UNO (ver paso 5)
            for d in divisions:
                for idx in range(1, teams_per_div + 1):
                    team = Team.objects.create(event=event, division=d, name=f"Team{idx}")
                    uname = f"ath_{slug}_{d.id}_{idx}"
                    email = f"{uname}@example.com"
                    user = ensure_demo_user(uname, email)
                    entry_kwargs = {"event": event, "division": d}
                    if has_field(AthleteEntry, "team"):
                        entry_kwargs["team"] = team
                    if has_field(AthleteEntry, "first_name"):
                        entry_kwargs["first_name"] = f"Ath-{idx}"
                    if has_field(AthleteEntry, "last_name"):
                        entry_kwargs["last_name"] = "Demo"
                    if has_field(AthleteEntry, "user"):
                        entry_kwargs["user"] = user
                    entry = AthleteEntry.objects.create(**entry_kwargs)
                    rosters[d.id].append((team, entry))
            self.stdout.write(self.style.SUCCESS("✓ Atletas/Equipos de demo creados"))
        elif AthleteEntry:
            for d in divisions:
                for idx in range(1, teams_per_div + 1):
                    uname = f"ath_{slug}_{d.id}_{idx}"
                    email = f"{uname}@example.com"
                    user = ensure_demo_user(uname, email)
                    entry_kwargs = {"event": event, "division": d}
                    if has_field(AthleteEntry, "first_name"):
                        entry_kwargs["first_name"] = f"Ath-{idx}"
                    if has_field(AthleteEntry, "last_name"):
                        entry_kwargs["last_name"] = "Demo"
                    if has_field(AthleteEntry, "user"):
                        entry_kwargs["user"] = user
                    entry = AthleteEntry.objects.create(**entry_kwargs)
                    rosters[d.id].append((None, entry))
            self.stdout.write(self.style.SUCCESS("✓ Atletas de demo creados"))
        elif Team:
            for d in divisions:
                for idx in range(1, teams_per_div + 1):
                    team = Team.objects.create(event=event, division=d, name=f"Team{idx}")
                    rosters[d.id].append((team, None))
            self.stdout.write(self.style.SUCCESS("✓ Equipos de demo creados"))
        else:
            self.stdout.write(self.style.WARNING("• No hay modelos Team/AthleteEntry — no se podrán crear asignaciones"))

        # 5) Heats + ASIGNACIONES (exactamente UNO: athlete_entry O team)
        for w in wods:
            for d in divisions:
                # Cómo repartimos participantes por heats
                total = len(rosters[d.id])
                for h in range(1, heats_per_div + 1):
                    heat_kwargs = {"workout": w, "division": d}
                    if has_field(WorkoutHeat, "heat_number"):
                        heat_kwargs["heat_number"] = h
                    set_if_has(heat_kwargs, WorkoutHeat, capacity=lanes)
                    heat = WorkoutHeat.objects.create(**heat_kwargs)

                    start = (h - 1) * lanes
                    end = min(start + lanes, total)
                    for lane, idx in enumerate(range(start, end), start=1):
                        team, entry = rosters[d.id][idx]
                        assign_kwargs = {"heat": heat}
                        if has_field(HeatAssignment, "lane"):
                            assign_kwargs["lane"] = lane

                        # REGLA CLAVE: asignar exactamente UNO
                        if entry is not None and has_field(HeatAssignment, "athlete_entry"):
                            assign_kwargs["athlete_entry"] = entry
                        elif team is not None and has_field(HeatAssignment, "team"):
                            assign_kwargs["team"] = team
                        else:
                            # Si no hay ninguno disponible, salta (evita violar validación)
                            continue

                        HeatAssignment.objects.create(**assign_kwargs)
        self.stdout.write(self.style.SUCCESS("✓ Heats y asignaciones creadas (regla de uno cumplida)"))

        # 6) Scores (si aplica)
        if seed_scores and ScoreSubmission:
            rng = random.Random(42)
            created = 0
            for w in wods:
                for d in divisions:
                    assigns = (
                        HeatAssignment.objects
                        .filter(heat__workout=w, heat__division=d)
                        .select_related("heat")
                        .order_by("heat__id", "id")
                    )
                    rank = 1
                    for a in assigns:
                        s_kwargs = {}
                        set_if_has(
                            s_kwargs, ScoreSubmission,
                            event=event, workout=w, division=d,
                            raw_result=f"{rng.randint(120,720)} sec",
                            points=max(0, 100-rank), rank=rank,
                            status="confirmed"
                        )
                        if s_kwargs:
                            ScoreSubmission.objects.create(**s_kwargs)
                            created += 1
                            rank += 1
            self.stdout.write(self.style.SUCCESS(f"✓ {created} scores creados"))

        self.stdout.write(self.style.SUCCESS("✔ Demo lista."))