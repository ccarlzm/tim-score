from __future__ import annotations

from datetime import date

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from compcore.apps.accounts.models import Profile
from compcore.apps.events.models import Division, Event
from compcore.apps.registration.models import AthleteEntry, Team


def _age_on(dob, ref_date: date | None) -> int | None:
    if not dob or not ref_date:
        return None
    return ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))


class IndividualRegistrationForm(forms.Form):
    division = forms.ModelChoiceField(queryset=Division.objects.none(), empty_label="Selecciona división")

    def __init__(self, *args, **kwargs):
        event: Event = kwargs.pop('event')
        user: User = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['division'].queryset = Division.objects.filter(event=event, team_size=1).order_by('name')
        self.event = event
        self.user = user

    def clean_division(self):
        d: Division = self.cleaned_data['division']
        # Validación de edad si aplica
        prof = getattr(self.user, 'profile', None)
        if d.min_age or d.max_age:
            if not prof or not prof.date_of_birth:
                raise ValidationError("Completa tu fecha de nacimiento en el perfil para inscribirte en esta división.")
            age = _age_on(prof.date_of_birth, timezone.localdate())
            if d.min_age and age < d.min_age:
                raise ValidationError(f"Edad mínima {d.min_age}.")
            if d.max_age and age > d.max_age:
                raise ValidationError(f"Edad máxima {d.max_age}.")
        return d


class TeamCreateForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['division', 'name']

    def __init__(self, *args, **kwargs):
        event: Event = kwargs.pop('event')
        super().__init__(*args, **kwargs)
        self.fields['division'].queryset = Division.objects.filter(event=event, team_size__gt=1).order_by('name')


class TeamJoinForm(forms.Form):
    join_code = forms.CharField(max_length=8, label="Código de unión")


@login_required
def register(request, slug: str):
    event = get_object_or_404(Event, slug=slug)
    if not event.is_registration_open:
        messages.error(request, "La inscripción no está disponible en este momento.")
        return redirect('event_detail', slug=slug)

    if request.method == 'POST':
        form = IndividualRegistrationForm(request.POST, event=event, user=request.user)
        if form.is_valid():
            division = form.cleaned_data['division']
            entry, created = AthleteEntry.objects.get_or_create(
                user=request.user, event=event, division=division, team=None
            )
            if created:
                messages.success(request, "Inscripción individual exitosa.")
            else:
                messages.info(request, "Ya estabas inscrito en esta división.")
            return redirect('registration_success', slug=slug)
    else:
        form = IndividualRegistrationForm(event=event, user=request.user)

    return render(request, 'registration/register.html', {'event': event, 'form': form})


@login_required
def register_success(request, slug: str):
    event = get_object_or_404(Event, slug=slug)
    return render(request, 'registration/success.html', {'event': event})


@login_required
def team_create(request, slug: str):
    event = get_object_or_404(Event, slug=slug)
    if not event.is_registration_open:
        messages.error(request, "La inscripción no está disponible en este momento.")
        return redirect('event_detail', slug=slug)

    if request.method == 'POST':
        form = TeamCreateForm(request.POST, event=event)
        if form.is_valid():
            team: Team = form.save(commit=False)
            team.event = event
            team.captain = request.user
            team.save()
            # inscribir capitán
            AthleteEntry.objects.get_or_create(user=request.user, event=event, division=team.division, team=team)
            messages.success(request, f"Equipo '{team.name}' creado. Código de unión: {team.join_code}")
            return render(request, 'registration/team_create.html', {'event': event, 'form': form, 'team': team})
    else:
        form = TeamCreateForm(event=event)

    return render(request, 'registration/team_create.html', {'event': event, 'form': form})


@login_required
def team_join(request, slug: str):
    event = get_object_or_404(Event, slug=slug)
    if not event.is_registration_open:
        messages.error(request, "La inscripción no está disponible en este momento.")
        return redirect('event_detail', slug=slug)

    if request.method == 'POST':
        form = TeamJoinForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['join_code'].upper().strip()
            team = get_object_or_404(Team, event=event, join_code=code)
            entry = AthleteEntry(user=request.user, event=event, division=team.division, team=team)
            try:
                entry.save()
            except ValidationError as e:
                form.add_error(None, e.message)
            else:
                messages.success(request, f"Te uniste al equipo '{team.name}'.")
                return redirect('registration_success', slug=slug)
    else:
        form = TeamJoinForm()

    return render(request, 'registration/team_join.html', {'event': event, 'form': form})