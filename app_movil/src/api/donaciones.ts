import { apiFetch } from "./client";

export type Donacion = { estado: string; monto: string; fecha_creacion: string };

// A diferencia de Donacion (DonacionActualSerializer, sin id -- es la
// suscripción activa, un solo objeto), cada Pago del historial sí tiene
// id (PagoResumenSerializer) -- lo necesita la app para usarlo como key
// de lista en vez del índice del array (Sonar typescript:S6479).
export type Pago = Donacion & { id: number };

export type MiDonacion = {
  donacion_actual: Donacion | null;
  pagos: Pago[];
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
// siempre trae datos ICU completos. Agrupa de a 3 dígitos por loop (no
// por regex) -- la regex anterior, /\B(?=(\d{3})+(?!\d))/g, tenía
// backtracking super-lineal (Sonar typescript:S8786).
export function formatearMontoDonacion(valorStr: string): string {
  const entero = Math.round(Number.parseFloat(valorStr)).toString();
  const grupos: string[] = [];
  let resto = entero;
  while (resto.length > 3) {
    grupos.unshift(resto.slice(-3));
    resto = resto.slice(0, -3);
  }
  grupos.unshift(resto);
  return grupos.join(".");
}
