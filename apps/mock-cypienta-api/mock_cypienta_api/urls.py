from django.urls import path

from usage_api import views

urlpatterns = [
    path("health", views.health),
    path("api/user/info", views.user_info),
    path("api/user/actions", views.actions),
]

handler400 = "usage_api.views.bad_request"
handler403 = "usage_api.views.permission_denied"
handler404 = "usage_api.views.not_found"
handler500 = "usage_api.views.server_error"
