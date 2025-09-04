from django.db import models
from compcore.apps.registration.models import AthleteEntry
from compcore.apps.events.models import Workout

class ScoreSubmission(models.Model):
    entry = models.ForeignKey(AthleteEntry, on_delete=models.CASCADE)
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE)
    raw_value = models.CharField(max_length=64)  # e.g., '07:43' or '185' or '126'
    tie_break = models.CharField(max_length=32, blank=True)
    status = models.CharField(max_length=12, default='PENDING')  # PENDING/APPROVED/REJECTED
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry} – {self.workout} = {self.raw_value}"
