import { apiFetch } from "./client";

export type Donacion = { estado: string; monto: string; fecha_creacion: string };

export type MiDonacion = {
  donacion_actual: Donacion | null;
  pagos: Donacion[];
  total_donado: string;
  cantidad_aportes: number;
};

export function obtenerMiDonacion(): Promise<MiDonacion> {
  return apiFetch<MiDonacion>("/api/v1/pagos/mi-donacion/");
}

export function crearDonacion(): Promise<{ url_autorizacion: string }> {
  return apiFetch<{ url_autorizacion: string }>("/api/v1/pagos/donar/", { method: "POST" });
}

export function cancelarDonacion(): Promise<void> {
  return apiFetch<void>("/api/v1/pagos/donar/cancelar/", { method: "POST" });
}

// Mismo criterio que usan los propios endpoints del backend (pagos/api_views.py):
// donar/cancelar aceptan "pendiente" o "autorizada" -- cualquier otro
// estado (o ninguna donación) es elegible para donar de nuevo. Hallazgo
// Critical ya corregido una vez en la pantalla Donar (antes se decidía
// solo por "¿hay donacion_actual?", dejando a alguien viendo "Cancelar"/
// "activa" para siempre con una donación cancelada o pausada) y vuelto a
// aparecer en la pantalla principal por tener su propia copia del
// criterio -- se exporta acá como única fuente de verdad para que no
// vuelva a divergir.
export const ESTADOS_DONACION_CANCELABLES = new Set(["pendiente", "autorizada"]);

// Monto sin decimales, con "." como separador de miles -- evita depender
// de Intl/toLocaleString, que en Hermes (runtime real del teléfono) no
// siempre trae datos ICU completos.
export function formatearMontoDonacion(valorStr: string): string {
  const entero = Math.round(parseFloat(valorStr)).toString();
  return entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}
