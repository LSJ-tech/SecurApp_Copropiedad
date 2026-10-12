from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class UsuarioOCorreoBackend(ModelBackend):
    """Permite iniciar sesión con el username o con el email -- muchos
    residentes no recuerdan su username autogenerado (ej. "jlroman2"), pero
    sí su correo (obligatorio y único al autoregistrarse o al ser creados
    por directiva/administración -- ver RegistroResidenteForm/CrearMiembroForm).

    No usa get() con el OR directo porque User.email no tiene unique=True a
    nivel de base de datos (la unicidad se valida solo en esos formularios),
    así que en teoría podría haber más de un candidato -- se prueba la
    contraseña contra cada uno en vez de asumir que hay como máximo uno.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        modelo_usuario = get_user_model()
        candidatos = list(modelo_usuario._default_manager.filter(Q(username__iexact=username) | Q(email__iexact=username)))
        for user in candidatos:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user
        if not candidatos:
            # Mismo truco que ModelBackend.authenticate(): corre el hasher
            # igual aunque no haya usuario, para que el tiempo de respuesta
            # no delate si el username/correo existe o no.
            modelo_usuario().set_password(password)
        return None
