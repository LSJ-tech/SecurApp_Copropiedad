import { apiFetch } from "./client";

export type AvisoOut = {
  id: number;
  titulo: string;
  cuerpo: string;
  fecha_creacion: string;
  autor_nombre: string | null;
  torre_nombre: string | null;
  leido_por_count: number | null;
  total_destinatarios: number | null;
};

export function listarAvisos(): Promise<AvisoOut[]> {
  return apiFetch<AvisoOut[]>("/api/v1/avisos/");
}

export function marcarLeido(id: number): Promise<AvisoOut> {
  return apiFetch<AvisoOut>(`/api/v1/avisos/${id}/marcar_leido/`, { method: "POST" });
}

export function crearAviso(payload: { titulo: string; cuerpo: string }): Promise<AvisoOut> {
  return apiFetch<AvisoOut>("/api/v1/avisos/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
