import { apiFetch } from "./client";

export type Miembro = {
  id: number;
  nombre: string;
  rol: "residente" | "delegado";
  rol_display: string;
  unidad_numero: string | null;
  unidad_torre: string | null;
};

export type CrearMiembroPayload = {
  nombre: string;
  apellido: string;
  email: string;
  rol: "residente" | "delegado";
  unidad?: number;
};

export type CrearMiembroResultado = {
  id: number;
  username: string;
  password_temporal: string;
};

type PaginaDRF<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export async function listarMiembros(): Promise<Miembro[]> {
  const pagina = await apiFetch<PaginaDRF<Miembro>>("/api/v1/miembros/");
  return pagina.results;
}

export function crearMiembro(payload: CrearMiembroPayload): Promise<CrearMiembroResultado> {
  return apiFetch<CrearMiembroResultado>("/api/v1/miembros/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
