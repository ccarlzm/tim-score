from django.db import models
from django.contrib.auth.models import User

class Profile(models.Model):
    SEX_CHOICES = (
        ("M", "Masculino"),
        ("F", "Femenino"),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    gym = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=32, blank=True)

    # Documento único (lo dejamos opcional para no bloquear seeds antiguos)
    id_document = models.CharField("Documento de identidad", max_length=64, unique=True, null=True, blank=True)
    date_of_birth = models.DateField("Fecha de nacimiento", null=True, blank=True)

    # NUEVO: sexo
    sex = models.CharField("Sexo", max_length=1, choices=SEX_CHOICES, null=True, blank=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username