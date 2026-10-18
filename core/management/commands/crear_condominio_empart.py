from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Condominio, Membresia, Torre, Unidad
from core.usuarios import generar_password_temporal, generar_username

NUMEROS_POR_PISO = ["1", "2", "3", "4"]
PISOS = ["1", "2", "3", "4", "5"]
TORRES = [str(n) for n in range(1, 16)]


class Command(BaseCommand):
    help = "Crea el Condominio EMPART (15 torres x 5 pisos x 4 deptos = 300 unidades) con datos reales."

    def handle(self, *args, **options):
        with transaction.atomic():
            condominio = self._crear_condominio()
            self._crear_torres_y_unidades(condominio)
            self._crear_residente_ejemplo(condominio)
            self._crear_directiva(condominio)

    def _crear_condominio(self):
        condominio, creado = Condominio.objects.get_or_create(
            nombre="Condominio EMPART",
            defaults={
                "direccion": "Porvenir 1602, Playa Ancha",
                "comuna": "Valparaíso",
                "region": "valparaiso",
                "plan": "premium",
            },
        )
        if creado:
            self.stdout.write(self.style.SUCCESS(f"Condominio creado: {condominio}"))
        else:
            self.stdout.write(f"Condominio ya existía: {condominio}")
        return condominio

    def _crear_torres_y_unidades(self, condominio):
        total_creadas = 0
        for nombre_torre in TORRES:
            torre, _ = Torre.objects.get_or_create(condominio=condominio, nombre=nombre_torre)
            for piso in PISOS:
                for posicion in NUMEROS_POR_PISO:
                    numero = f"{piso}{posicion}"
                    _, creada = Unidad.objects.get_or_create(condominio=condominio, torre=torre, numero=numero)
                    if creada:
                        total_creadas += 1
        self.stdout.write(self.style.SUCCESS(f"{total_creadas} unidades nuevas creadas (total esperado: 300)."))

    def _crear_residente_ejemplo(self, condominio):
        torre_9 = Torre.objects.get(condominio=condominio, nombre="9")
        unidad_54 = Unidad.objects.get(condominio=condominio, torre=torre_9, numero="54")

        if Membresia.objects.filter(unidad=unidad_54).exists():
            self.stdout.write("Ya existe un miembro asignado a Torre 9, depto 54 — no se crea otro.")
            return

        username = generar_username("Logan", "Silva", "Jara")
        password = generar_password_temporal()
        user = User.objects.create_user(
            username=username, password=password,
            first_name="Logan", last_name="Silva Jara",
            email="logan.silva.jara@gmail.com",
        )
        Membresia.objects.create(user=user, condominio=condominio, unidad=unidad_54, rol="residente")
        self.stdout.write(self.style.SUCCESS(
            f"Usuario residente creado para Torre 9, depto 54 — usuario «{username}», contraseña temporal «{password}»."
        ))

    def _crear_directiva(self, condominio):
        """Nombre del método histórico -- ya no crea una cuenta "directiva"
        (rol retirado), ahora es is_staff=True (devquad), sin Membresia."""
        if User.objects.filter(first_name="Administración", last_name="EMPART", is_staff=True).exists():
            self.stdout.write("Ya existe una cuenta devquad para EMPART — no se crea otra.")
            return

        username = generar_username("Administración", "EMPART")
        password = generar_password_temporal()
        User.objects.create_user(
            username=username, password=password, is_staff=True,
            first_name="Administración", last_name="EMPART",
        )
        self.stdout.write(self.style.SUCCESS(
            f"Usuario devquad (administración) creado — usuario «{username}», contraseña temporal «{password}»."
        ))
