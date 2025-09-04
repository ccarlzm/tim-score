from django.apps import AppConfig
from django.db.models.signals import post_migrate


def ensure_judges_group(sender, **kwargs):
    # Crea el grupo "judges" si no existe (idempotente)
    from django.contrib.auth.models import Group
    Group.objects.get_or_create(name="judges")


class JudgingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'compcore.apps.judging'

    def ready(self):
        # Conectamos el hook post_migrate una sola vez
        post_migrate.connect(ensure_judges_group, dispatch_uid="judging.ensure_judges_group")