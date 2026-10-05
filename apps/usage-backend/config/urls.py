from django.urls import include, path

from usage import views

urlpatterns = [
    path("", views.index, name="index"),
    path("health", views.health, name="health"),
    path("health/ready", views.readiness, name="readiness"),
    path("api/", include("usage.urls")),
]

handler400 = "core.errors.bad_request"
handler403 = "core.errors.permission_denied"
handler404 = "core.errors.not_found"
handler500 = "core.errors.server_error"
