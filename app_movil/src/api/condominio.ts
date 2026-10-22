import { apiFetch } from "./client";

export type CondominioEdicion = {
  nombre: string;
  etiqueta_organizacion: string;
  direccion: string;
  comuna: string;
  region: string;
  datos_transferencia: string;
  etiqueta_torre: string;
  etiqueta_unidad: string;
  genero_unidad: "f" | "m";
};

export function obtenerMiCondominio(): Promise<CondominioEdicion> {
  return apiFetch<CondominioEdicion>("/api/v1/condominio/");
}

export function actualizarMiCondominio(datos: Partial<CondominioEdicion>): Promise<CondominioEdicion> {
  return apiFetch<CondominioEdicion>("/api/v1/condominio/", {
    method: "PATCH",
    body: JSON.stringify(datos),
  });
}

export function regenerarCodigoInvitacion(): Promise<{ token_registro_residentes: string }> {
  return apiFetch<{ token_registro_residentes: string }>("/api/v1/condominio/regenerar-token/", {
    method: "POST",
  });
}
