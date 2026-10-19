from django.db import migrations

from core.usuarios import generar_codigo_invitacion


def regenerar_tokens(apps, schema_editor):
    """La migración anterior solo cambió el tipo de columna (de uuid a
    varchar) -- el valor que queda ahí es el UUID viejo truncado a 20
    caracteres, no un código corto de verdad. Acá se le asigna a cada
    condominio un código nuevo (invalida los links/QR ya compartidos,
    mismo efecto que "Generar link nuevo" pero para todos a la vez --
    aceptado a propósito, ver conversación)."""
    Condominio = apps.get_model("core", "Condominio")
    for condominio in Condominio.objects.all():
        condominio.token_registro_residentes = generar_codigo_invitacion()
        condominio.save(update_fields=["token_registro_residentes"])


def no_revertir(apps, schema_editor):
    """No tiene sentido "volver" a un UUID -- la migración anterior ya
    truncó esos valores, no hay nada que recuperar."""


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0023_alter_condominio_token_registro_residentes"),
    ]

    operations = [
        migrations.RunPython(regenerar_tokens, no_revertir),
    ]
