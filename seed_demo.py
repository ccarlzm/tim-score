from django.contrib.auth.models import User
from compcore.apps.events.models import Event, Division, Workout
from compcore.apps.registration.models import AthleteEntry, Team
from compcore.apps.scoring.models import ScoreSubmission

# --- Config ---
EVENT_NAME = "Force Games"
EVENT_SLUG = "force-games"

# --- Helpers ---
def mk_user(email, first, last):
    u, _ = User.objects.get_or_create(
        username=email,
        defaults={"email": email, "first_name": first, "last_name": last}
    )
    changed = False
    if u.first_name != first:
        u.first_name = first; changed = True
    if u.last_name != last:
        u.last_name = last; changed = True
    if u.email != email:
        u.email = email; changed = True
    if changed:
        u.save()
    return u

def mk_entry(user, event, division, *, team=None, paid=True):
    e, _ = AthleteEntry.objects.get_or_create(
        user=user, event=event,
        defaults={"division": division, "team": team, "paid": paid}
    )
    changed = False
    if e.division_id != division.id:
        e.division = division; changed = True
    if team and e.team_id != team.id:
        e.team = team; changed = True
    if changed:
        e.save()
    return e

def submit(entry, workout, raw, status="APPROVED", tie_break=""):
    ScoreSubmission.objects.create(entry=entry, workout=workout,
                                   raw_value=str(raw), tie_break=tie_break,
                                   status=status)

def fmt_time(seconds:int) -> str:
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"

# --- 1) Evento ---
event, _ = Event.objects.get_or_create(
    slug=EVENT_SLUG,
    defaults={"name": EVENT_NAME, "status": "OPEN"}
)

# --- 2) Divisiones ---
rx, _     = Division.objects.get_or_create(event=event, name="Rx",       defaults={"team_size": 1})
teams2, _ = Division.objects.get_or_create(event=event, name="Teams 2",  defaults={"team_size": 2})

# --- 3) Workouts ---
w1, _ = Workout.objects.get_or_create(event=event, order=1,
                                      defaults={"title":"WOD 1 - AMRAP 6", "scoring_type":"REPS", "cap_time_seconds":360})
w2, _ = Workout.objects.get_or_create(event=event, order=2,
                                      defaults={"title":"WOD 2 - 1RM Clean", "scoring_type":"LOAD", "cap_time_seconds":0})
w3, _ = Workout.objects.get_or_create(event=event, order=3,
                                      defaults={"title":"WOD 3 - 2K Row", "scoring_type":"TIME", "cap_time_seconds":900})

# Limpia scores previos del evento (para que sea repetible)
ScoreSubmission.objects.filter(workout__event=event).delete()

# --- 4) PARTICIPANTES: INDIVIDUAL (10 atletas en Rx) ---
names = [
    ("Alex","Rey"), ("Bruno","Díaz"), ("Carla","Paz"), ("Dani","Ríos"), ("Eva","Luna"),
    ("Fabio","Gil"), ("Gina","Vera"), ("Hugo","Mora"), ("Iris","Sol"), ("Javi","Rojo"),
]
ind_entries = []
for i,(first,last) in enumerate(names, start=1):
    u = mk_user(f"ind{i}@force.test", first, last)
    ind_entries.append(mk_entry(u, event, rx))

# Puntajes: para REPS/LOAD mayor es mejor; para TIME menor es mejor
for idx, e in enumerate(ind_entries, start=1):
    reps = 200 - (idx-1)*10           # 200, 190, 180, ...
    submit(e, w1, reps)

    load = 300 - (idx-1)*10           # 300, 290, 280, ...
    submit(e, w2, load)

    t_secs = 7*60 + (idx-1)*10        # 7:00, 7:10, 7:20, ...
    submit(e, w3, fmt_time(t_secs))

# --- 5) PARTICIPANTES: EQUIPOS (3 equipos de 2) ---
teams_data = {
    "Team Alpha": [("Ana","López"), ("Luis","Cruz")],
    "Team Beta":  [("Beto","Núñez"), ("Mara","Gómez")],
    "Team Gamma": [("Gus","Pardo"), ("Nora","Ibarra")],
}
team_entries_for_scoring = []  # usaremos el primer miembro como "mejor" del team

for tname, members in teams_data.items():
    team, _ = Team.objects.get_or_create(event=event, division=teams2, name=tname)
    first_member_entry = None
    for j,(first,last) in enumerate(members, start=1):
        u = mk_user(f"{tname.lower().replace(' ','')}{j}@force.test", first, last)
        e = mk_entry(u, event, teams2, team=team)
        if first_member_entry is None:
            first_member_entry = e
    team_entries_for_scoring.append((tname, first_member_entry))

# Scores de equipos: Alpha > Beta > Gamma
for pos, (tname, e) in enumerate(team_entries_for_scoring, start=1):
    reps = 220 - (pos-1)*10           # 220, 210, 200
    submit(e, w1, reps)

    load = 310 - (pos-1)*10           # 310, 300, 290
    submit(e, w2, load)

    t_secs = 6*60 + 40 + (pos-1)*10   # 6:40, 6:50, 7:00
    submit(e, w3, fmt_time(t_secs))

print("✅ Datos demo cargados. Revisa /leaderboard/force-games/")