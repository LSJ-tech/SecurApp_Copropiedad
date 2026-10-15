from django.urls import path

from . import views

urlpatterns = [
    path("vecindario/registro/", views.RegistroVecinoView.as_view(), name="vecindario-registro"),
    path("mi-barrio/", views.MiBarrioView.as_view(), name="mi-barrio"),
]
