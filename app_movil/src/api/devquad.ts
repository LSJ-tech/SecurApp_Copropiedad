import { apiFetch } from "./client";

export type CondominioResumen = {
  id: number;
  nombre: string;
  plan: string;
  puede_operar: boolean;
};

export type EntrarCondominioOut = {
  access: string;
  refresh: string;
  condominio: CondominioResumen;
};

export function listarCondominiosDevquad(): Promise<CondominioResumen[]> {
  return apiFetch<CondominioResumen[]>("/api/v1/devquad/condominios/");
}

export function entrarCondominio(id: number, refresh: string): Promise<EntrarCondominioOut> {
  return apiFetch<EntrarCondominioOut>(`/api/v1/devquad/condominios/${id}/entrar/`, {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
}
