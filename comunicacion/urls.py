from django.urls import path

from . import views

urlpatterns = [
    path("muro/", views.MuroVecinosView.as_view(), name="muro-vecinos"),
]
