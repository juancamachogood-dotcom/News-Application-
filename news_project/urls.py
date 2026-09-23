from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.views.generic import RedirectView

from news.views import signup

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(url="/accounts/login/", permanent=False)),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path("accounts/signup/", signup, name="signup"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("news.urls")),
]
