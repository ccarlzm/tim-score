from django.test import TestCase
from django.contrib.auth import get_user_model
from compcore.apps.events.models import Event, Division, Workout

User = get_user_model()

class SmokeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Usuario juez
        cls.judge = User.objects.create_user(
            username="judge_v3",
            email="judge@example.com",
            password="Pass1234!"
        )
        # Evento mínimo válido
        cls.event = Event.objects.create(
            name="Test Event",
            slug="test-event",
            status="open",
            start_date="2025-01-01",
            end_date="2025-01-02",
            registration_open=True,
            registration_deadline="2025-01-01",
        )
        # División
        cls.division = Division.objects.create(
            event=cls.event,
            name="RX Femenino — Individual",
            team_size=1,
            capacity_individuals=20,
            capacity_teams=0,
            male_quota=0,
            female_quota=20,
            min_age=16,
            max_age=99,
            heat_capacity=8,
        )
        # Workout
        cls.workout = Workout.objects.create(
            event=cls.event,
            order=1,
            title="WOD 1 — AMRAP 12",
            scoring_type="time",
            cap_time_seconds=12 * 60,
        )

    def test_home(self):
        r = self.client.get("/")
        self.assertGreaterEqual(r.status_code, 200)
        self.assertLess(r.status_code, 400)

    def test_event_detail(self):
        r = self.client.get(f"/events/{self.event.slug}/")
        self.assertGreaterEqual(r.status_code, 200)
        self.assertLess(r.status_code, 400)

    def test_leaderboard_event(self):
        r = self.client.get(f"/leaderboard/{self.event.slug}/")
        self.assertGreaterEqual(r.status_code, 200)
        self.assertLess(r.status_code, 400)

    def test_judging_requires_login(self):
        r = self.client.get("/judging/")
        self.assertIn(r.status_code, (301, 302))

    def test_judging_with_login(self):
        self.client.login(username="judge_v3", password="Pass1234!")
        r = self.client.get("/judging/")
        self.assertGreaterEqual(r.status_code, 200)
        self.assertLess(r.status_code, 400)