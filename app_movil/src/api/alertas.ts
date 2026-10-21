import { apiFetch } from "./client";

export type AlertaOut = {
  id: number;
  condominio_nombre: string;
  tipo: string;
  tipo_display: string;
  estado: "activa" | "resuelta" | "falsa_alarma" | "auto_cerrada";
  estado_display: string;
  mensaje: string;
  latitud: string | null;
  longitud: string | null;
  fecha_creacion: string;
  autor_nombre: string;
  autor_unidad: string | null;
  autor_torre: string | null;
  resuelta_por: number | null;
  resuelta_por_nombre: string | null;
  resuelta_por_unidad: string | null;
  fecha_resolucion: string | null;
  visto_por_count: number | null;
};

export function crearAlerta(payload: {
  tipo: string;
  mensaje?: string;
  latitud?: number | null;
  longitud?: number | null;
}): Promise<AlertaOut> {
  return apiFetch<AlertaOut>("/api/v1/alertas/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function resolverAlerta(id: number, estado: "resuelta" | "falsa_alarma"): Promise<AlertaOut> {
  return apiFetch<AlertaOut>(`/api/v1/alertas/${id}/resolver/`, {
    method: "PATCH",
    body: JSON.stringify({ estado }),
  });
}

export function obtenerAlerta(id: number): Promise<AlertaOut> {
  return apiFetch<AlertaOut>(`/api/v1/alertas/${id}/`);
}

export function listarAlertas(estado?: string): Promise<AlertaOut[]> {
  return apiFetch<AlertaOut[]>(estado ? `/api/v1/alertas/?estado=${estado}` : "/api/v1/alertas/");
}

export function marcarVisto(id: number): Promise<AlertaOut> {
  return apiFetch<AlertaOut>(`/api/v1/alertas/${id}/marcar_visto/`, { method: "POST" });
}
