from notificaciones.services import enviar_push_a_condominio, enviar_web_push_a_condominio

TITULOS_POR_TIPO = {
    "robo": "🚨 Alerta de robo",
    "incendio": "🔥 Alerta de incendio",
    "accidente": "🚑 Alerta de accidente",
    "emergencia_medica": "🚑 Alerta de emergencia médica",
    "persona_extrana": "⚠️ Persona extraña en el sector",
    "fuga_gas": "⚠️ Fuga de gas",
    "fuga_agua": "💧 Fuga o inundación de agua",
    "atrapado_ascensor": "🛗 Persona atrapada en ascensor",
    "objeto_sospechoso": "⚠️ Objeto o paquete sospechoso",
    "rina_disturbio": "🚨 Riña o disturbio",
    "otro": "🚨 Alerta de emergencia",
    "prueba": "🧪 Prueba del botón de pánico (no es una emergencia real)",
}


def notificar_alerta(alerta):
    """Avisa a todo el condominio del autor y, si tiene condominios_vecinos
    (comparten vecindario, ver Condominio.ids_red_alertas), también a ellos
    -- con el nombre del condominio de origen en el cuerpo, para que no se
    confundan pensando que la alerta es de su propio edificio."""
    titulo = TITULOS_POR_TIPO.get(alerta.tipo, TITULOS_POR_TIPO["otro"])
    cuerpo = alerta.mensaje or f"{alerta.autor.user.get_full_name()} activó el botón de pánico."
    data = {"tipo": "alerta", "alerta_id": alerta.id}
    enviar_push_a_condominio(alerta.condominio, titulo, cuerpo, data=data, excluir_user_id=alerta.autor.user_id)
    enviar_web_push_a_condominio(alerta.condominio, titulo, cuerpo, data=data, excluir_user_id=alerta.autor.user_id)

    cuerpo_vecino = f"[{alerta.condominio.nombre}] {cuerpo}"
    for vecino in alerta.condominio.condominios_vecinos.all():
        enviar_push_a_condominio(vecino, titulo, cuerpo_vecino, data=data)
        enviar_web_push_a_condominio(vecino, titulo, cuerpo_vecino, data=data)
