from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, List

from compcore.apps.events.models import Event, Division, Workout, WorkoutHeat

@dataclass
class Params:
    start_time: time
    end_time: time
    lunch_start: Optional[time]
    lunch_end: Optional[time]
    briefing_min: int
    reset_min: int
    validation_min: int
    call_offset_min: int
    rest_base_min: int
    rest_factor: float
    block_cushion_min: int

@dataclass
class Slot:
    area: str
    division: str
    workout_order: int
    workout_title: str
    heat_number: int
    call_time: datetime
    start_time: datetime
    end_time: datetime
    t_heat_min: int
    notes: str = ""

def _combine(d: date, t: time) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second, t.microsecond)

def _push_past_lunch(current: datetime, p: Params, day: date) -> datetime:
    if not p.lunch_start or not p.lunch_end:
        return current
    ls = _combine(day, p.lunch_start)
    le = _combine(day, p.lunch_end)
    if current < ls:
        return current
    if ls <= current < le:
        return le
    return current

def _t_heat_minutes(cap_seconds: Optional[int], p: Params) -> int:
    cap_min = int((cap_seconds or 0) // 60)
    return cap_min + p.briefing_min + p.reset_min + p.validation_min

def _rest_minutes(cap_seconds: Optional[int], p: Params) -> int:
    cap_min = int((cap_seconds or 0) // 60)
    return max(p.rest_base_min, int(round(p.rest_factor * cap_min)))

class Scheduler:
    """
    Genera un cronograma (solo cálculo, no escribe en BD).
    Asume 1 área (Area A) y usa los WorkoutHeat existentes para saber cuántos heats por división.
    """

    def __init__(self, event: Event, params: Params):
        self.event = event
        self.p = params
        self.area_name = "Area A"

    def generate(self) -> Dict:
        day = self.event.start_date or date.today()
        current = _combine(day, self.p.start_time)

        # Validación ventana
        end_of_day = _combine(day, self.p.end_time)
        if self.p.lunch_start and self.p.lunch_end and self.p.lunch_start >= self.p.lunch_end:
            # si lunch está mal, lo ignoramos
            self.p.lunch_start = None
            self.p.lunch_end = None

        # Obtener workouts en orden y derivados
        workouts = list(Workout.objects.filter(event=self.event).order_by("order"))

        # Mapear heats por (workout -> division -> lista heat_number)
        heats_by_w_div: Dict[int, Dict[int, List[int]]] = {}
        for w in workouts:
            wb = heats_by_w_div.setdefault(w.order, {})
            for h in WorkoutHeat.objects.filter(workout=w).order_by("heat_number"):
                if h.division_id is None:
                    # Si por alguna razón falta división, lo omitimos
                    continue
                wb.setdefault(h.division_id, []).append(h.heat_number)

        # Divisiones presentes en al menos un heat de algún workout
        divisions = list(Division.objects.filter(event=self.event).order_by("name"))

        # Para descanso por división: track del último "end" programado por división
        last_end_by_div: Dict[int, datetime] = {}

        slots: List[Slot] = []
        notes_global: List[str] = []

        # Programación por bloques (W1, W2, ...)
        for w in workouts:
            # Cálculos por W
            t_heat_min = _t_heat_minutes(w.cap_time_seconds, self.p)
            rest_min = _rest_minutes(w.cap_time_seconds, self.p)

            # Divisiones que realmente tienen heats en este W
            divs_in_w = [d for d in divisions if heats_by_w_div.get(w.order, {}).get(d.id)]
            if not divs_in_w:
                # Nada que programar para este workout
                continue

            # Programamos las divisiones en orden por nombre para determinismo
            for div in divs_in_w:
                heats = heats_by_w_div[w.order][div.id]
                # Respetar descanso de la división vs su último fin (del W anterior)
                earliest = last_end_by_div.get(div.id)
                if earliest:
                    earliest = earliest + timedelta(minutes=rest_min)
                # Alinear current con descanso y con lunch
                if earliest and current < earliest:
                    current = earliest
                current = _push_past_lunch(current, self.p, day)

                # Insertar cada heat
                for hn in heats:
                    start = current
                    end = start + timedelta(minutes=t_heat_min)
                    call = start - timedelta(minutes=self.p.call_offset_min)

                    # No sobrepasar el fin del día; si no cabe, parar
                    if end > end_of_day:
                        notes_global.append(
                            f"No hay ventana suficiente para W{w.order} {div.name} H{hn} (corta el día)."
                        )
                        break

                    slots.append(Slot(
                        area=self.area_name,
                        division=div.name,
                        workout_order=w.order,
                        workout_title=w.title or f"W{w.order}",
                        heat_number=hn,
                        call_time=call,
                        start_time=start,
                        end_time=end,
                        t_heat_min=t_heat_min,
                        notes="",
                    ))

                    current = end  # siguiente heat contiguo

                # Al terminar la división en este W, actualizamos último fin
                last_end_by_div[div.id] = current

            # Colchón post bloque de W
            if self.p.block_cushion_min > 0:
                current = current + timedelta(minutes=self.p.block_cushion_min)
                current = _push_past_lunch(current, self.p, day)

        plan = {
            "event": self.event,
            "day": day,
            "slots": slots,
            "notes": notes_global,
            "params": self.p,
        }
        return plan