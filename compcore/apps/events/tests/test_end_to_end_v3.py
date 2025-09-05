from __future__ import annotations

from django.test import TestCase, Client
from django.core.management import call_command
from django.urls import reverse

from compcore.apps.events.models import Event, Workout, WorkoutHeat


class EndToEndV3Test(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo_event", "--event", "Force Games V3", "--slug", "force-games-v3", "--heats-per-division", "2", "--lanes", "6")

    def setUp(self):
        self.client = Client()
        self.event = Event.objects.get(slug="force-games-v3")

    def test_public_pages(self):
        r = self.client.get("/")
        self.assertLess(r.status_code, 400)

        r = self.client.get("/events/")
        self.assertLess(r.status_code, 400)

        r = self.client.get(f"/events/{self.event.slug}/")
        self.assertLess(r.status_code, 400)

        wod = Workout.objects.filter(event=self.event).first()
        self.assertIsNotNone(wod)
        r = self.client.get(f"/heats/{self.event.slug}/w{wod.order}/")
        self.assertLess(r.status_code, 400)

        r = self.client.get("/leaderboard/")
        self.assertLess(r.status_code, 400)

        r = self.client.get(f"/leaderboard/live/{self.event.slug}/w{wod.order}/")
        self.assertLess(r.status_code, 400)

    def test_judging_protected(self):
        # Sin login debe bloquear o redirigir
        r = self.client.get("/judging/")
        self.assertIn(r.status_code, (302, 403))

        # Crear staff y loguear
        call_command("seed_demo_event", "--slug", "force-games-v3", "--create-staff")
        self.client.login(username="judge", password="Pass1234!")

        r = self.client.get("/judging/")
        self.assertLess(r.status_code, 400)

        heat = WorkoutHeat.objects.filter(workout__event=self.event).first()
        if heat:
            r = self.client.get(f"/judging/{self.event.slug}/w{heat.workout.order}/d{heat.division.id}/h{heat.heat_number}/")
            self.assertLess(r.status_code, 400)

            r = self.client.get(f"/judging/{self.event.slug}/w{heat.workout.order}/d{heat.division.id}/h{heat.heat_number}/lane/1/")
            self.assertLess(r.status_code, 400)