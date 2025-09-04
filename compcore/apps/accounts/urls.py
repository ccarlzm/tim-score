from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path("login/",  views.CustomLoginView.as_view(), name="login"),
    path("logout/", views.auth_views.LogoutView.as_view(template_name="registration/logged_out.html"), name="logout"),

    # Password change
    path("password/change/",
         views.auth_views.PasswordChangeView.as_view(template_name="registration/password_change_form.html"),
         name="password_change"),
    path("password/change/done/",
         views.auth_views.PasswordChangeDoneView.as_view(template_name="registration/password_change_done.html"),
         name="password_change_done"),

    # Password reset
    path("password/reset/",
         views.auth_views.PasswordResetView.as_view(template_name="registration/password_reset_form.html"),
         name="password_reset"),
    path("password/reset/done/",
         views.auth_views.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
         name="password_reset_done"),
    path("password/reset/confirm/<uidb64>/<token>/",
         views.auth_views.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
         name="password_reset_confirm"),
    path("password/reset/complete/",
         views.auth_views.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
         name="password_reset_complete"),

    # Signup público (controlado por Event.allow_self_signup)
    path("signup/", views.signup, name="signup"),

    # Profile
    path("profile/", views.profile, name="accounts_profile"),
    path("profile/edit/", views.profile_edit, name="accounts_profile_edit"),
]