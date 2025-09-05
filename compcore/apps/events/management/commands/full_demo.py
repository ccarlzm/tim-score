from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.management import call_command

User = get_user_model()


class Command(BaseCommand):
    help = "Crea superuser, juez, evento demo, corre smoketest y muestra URLs clave"

    def handle(self, *args, **options):
        # Migraciones
        self.stdout.write(self.style.WARNING("▶ Ejecutando migrate..."))
        call_command("migrate", interactive=False)

        # Superuser
        if not User.objects.filter(username="admin").exists():
            self.stdout.write("▶ Creando superuser admin/admin ...")
            User.objects.create_superuser("admin", "admin@example.com", "admin")
        else:
            self.stdout.write("✓ Superuser admin ya existe")

        # Judge user
        if not User.objects.filter(username="judge_v3").exists():
            self.stdout.write("▶ Creando usuario judge_v3/Pass1234! ...")
            User.objects.create_user("judge_v3", "judge@example.com", "Pass1234!")
        else:
            self.stdout.write("✓ Usuario judge_v3 ya existe")

        # Evento demo
        slug = "force-games-v3-test_ok"
        self.stdout.write(f"▶ Sembrando evento demo '{slug}' ...")
        call_command(
            "seed_demo_event",
            "--event", "Force Games V3 (Test)",
            "--slug", slug,
            "--heats-per-division", "2",
            "--lanes", "6",
            "--teams-per-division", "5",
            "--workouts", "2",
            "--seed-scores"
        )

        # Smoketest
        self.stdout.write("▶ Corriendo smoketest...")
        try:
            call_command("smoketest_v3", "--slug", slug, "--login")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Smoketest falló: {e}"))

        self.stdout.write(self.style.SUCCESS("✔ Full demo lista"))
        self.stdout.write("")
        self.stdout.write("URLs clave:")
        self.stdout.write(" - Home:        http://127.0.0.1:8000/")
        self.stdout.write(f" - Events:      http://127.0.0.1:8000/events/{slug}/")
        self.stdout.write(f" - Leaderboard: http://127.0.0.1:8000/leaderboard/{slug}/")
        self.stdout.write(f" - Live:        http://127.0.0.1:8000/leaderboard/live/{slug}/w1/")
        self.stdout.write(f" - Heats:       http://127.0.0.1:8000/heats/{slug}/w1/")
        self.stdout.write(" - Judging:     http://127.0.0.1:8000/judging/")
        self.stdout.write(" - Admin:       http://127.0.0.1:8000/admin/")