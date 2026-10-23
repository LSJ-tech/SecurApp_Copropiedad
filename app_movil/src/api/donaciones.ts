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
