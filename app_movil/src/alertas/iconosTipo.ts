// Mapea cada valor de TIPOS_ALERTA a un ícono de Ionicons -- espejo del
// grid de botones con bi-* de inicio.html (core/templates/core/inicio.html),
// mismo criterio de ícono por tipo, traducido al set de Ionicons.
import type { ComponentProps } from "react";
import type { Ionicons } from "@expo/vector-icons";

type NombreIcono = ComponentProps<typeof Ionicons>["name"];

export const ICONO_POR_TIPO: Record<string, NombreIcono> = {
  robo: "shield-outline",
  incendio: "flame-outline",
  accidente: "bandage-outline",
  emergencia_medica: "pulse-outline",
  persona_extrana: "person-outline",
  fuga_gas: "warning-outline",
  fuga_agua: "water-outline",
  atrapado_ascensor: "swap-vertical-outline",
  objeto_sospechoso: "bag-outline",
  rina_disturbio: "people-outline",
  otro: "ellipsis-horizontal-outline",
  prueba: "bug-outline",
};
