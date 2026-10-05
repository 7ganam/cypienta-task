from django.urls import path

from . import views

urlpatterns = [
    path("csrf", views.csrf, name="csrf"),
    path("user/info", views.user_info, name="user-info"),
    path("user/actions", views.actions, name="actions"),
]
