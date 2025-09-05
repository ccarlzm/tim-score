# compcore/apps/orgs/views.py
from __future__ import annotations

from django.shortcuts import render
from django.utils import timezone

def dashboard(request):
    """
    Dashboard simple de organizaciones. De momento es informativo
    (no hay modelos definidos en orgs).
    """
    ctx = {
        "now": timezone.now(),
    }
    return render(request, "orgs/dashboard.html", ctx)