from notificaciones.services import enviar_push_a_condominio, enviar_web_push_a_condominio


def notificar_aviso(aviso):
    """Avisa a todo el condominio de un aviso nuevo de directiva/
    administración, sin molestar a quien mismo lo publicó."""
    titulo = "📢 Nuevo aviso"
    cuerpo = aviso.titulo
    data = {"tipo": "aviso", "aviso_id": aviso.id}
    enviar_push_a_condominio(aviso.condominio, titulo, cuerpo, data=data, excluir_user_id=aviso.autor.user_id)
    enviar_web_push_a_condominio(aviso.condominio, titulo, cuerpo, data=data, excluir_user_id=aviso.autor.user_id)
