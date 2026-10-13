from notificaciones.services import enviar_push_a_condominio, enviar_web_push_a_condominio


def notificar_aviso(aviso):
    """Avisa de un aviso nuevo -- a todo el condominio (directiva/
    administración), o solo a los residentes de la torre si lo publicó un
    delegado (ver Aviso.torre), sin molestar a quien mismo lo publicó."""
    titulo = "📢 Nuevo aviso"
    cuerpo = aviso.titulo
    data = {"tipo": "aviso", "aviso_id": aviso.id}
    enviar_push_a_condominio(
        aviso.condominio, titulo, cuerpo, data=data, excluir_user_id=aviso.autor.user_id, torre=aviso.torre,
    )
    enviar_web_push_a_condominio(
        aviso.condominio, titulo, cuerpo, data=data, excluir_user_id=aviso.autor.user_id, torre=aviso.torre,
    )
