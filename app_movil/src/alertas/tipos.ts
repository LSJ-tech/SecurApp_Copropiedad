// Espejo exacto de TIPO_CHOICES en alertas/models.py (backend) -- si se
// agrega un tipo nuevo allá, actualizar acá a mano.
export const TIPOS_ALERTA = [
  { valor: "robo", etiqueta: "Robo" },
  { valor: "incendio", etiqueta: "Incendio" },
  { valor: "accidente", etiqueta: "Accidente" },
  { valor: "emergencia_medica", etiqueta: "Emergencia médica" },
  { valor: "persona_extrana", etiqueta: "Persona extraña en el sector" },
  { valor: "fuga_gas", etiqueta: "Fuga de gas" },
  { valor: "fuga_agua", etiqueta: "Fuga o inundación de agua" },
  { valor: "atrapado_ascensor", etiqueta: "Persona atrapada en ascensor" },
  { valor: "objeto_sospechoso", etiqueta: "Objeto o paquete sospechoso" },
  { valor: "rina_disturbio", etiqueta: "Riña o disturbio" },
  { valor: "otro", etiqueta: "Otro" },
  { valor: "prueba", etiqueta: "Prueba" },
];
