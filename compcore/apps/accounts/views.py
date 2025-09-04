from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.conf import settings

from compcore.apps.events.models import Event
from .models import Profile


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ["gym", "phone", "id_document", "date_of_birth", "sex"]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}


def _ensure_profile(user: User) -> Profile:
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


class CustomLoginView(auth_views.LoginView):
    template_name = "registration/login.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        signup_enabled = Event.objects.filter(
            allow_self_signup=True, registration_open=True, status="OPEN"
        ).exists()
        ctx["signup_enabled"] = signup_enabled
        return ctx


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit)
        _ensure_profile(user)
        return user


def signup(request):
    # Habilitado solo si hay al menos un evento con allow_self_signup activo
    signup_enabled = Event.objects.filter(
        allow_self_signup=True, registration_open=True, status="OPEN"
    ).exists()
    if not signup_enabled:
        messages.error(request, "El auto-registro no está disponible en este momento.")
        return redirect("login")

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            next_url = request.GET.get("next") or request.POST.get("next") or reverse("home")
            # Seguridad del redirect
            if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                return redirect(next_url)
            return redirect("home")
    else:
        form = SignupForm()

    return render(request, "registration/signup.html", {"form": form})


def profile(request):
    from django.contrib.auth.decorators import login_required
    @login_required
    def _inner(req):
        profile = _ensure_profile(req.user)
        return render(req, "accounts/profile.html", {"user_obj": req.user, "profile": profile})
    return _inner(request)


def profile_edit(request):
    from django.contrib.auth.decorators import login_required
    @login_required
    def _inner(req):
        profile = _ensure_profile(req.user)
        if req.method == "POST":
            form = ProfileForm(req.POST, instance=profile)
            if form.is_valid():
                form.save()
                return redirect("accounts_profile")
        else:
            form = ProfileForm(instance=profile)
        return render(req, "accounts/profile_edit.html", {"user_obj": req.user, "profile": profile, "form": form})
    return _inner(request)