import { apiFetch } from "./client";

export type Unidad = {
  id: number;
  numero: string;
  calle: string;
  torre: number | null;
  alicuota: string | null;
};

type PaginaDRF<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export async function listarUnidades(): Promise<Unidad[]> {
  const pagina = await apiFetch<PaginaDRF<Unidad>>("/api/v1/unidades/");
  return pagina.results;
}

export function crearUnidad(payload: {
  numero: string;
  calle?: string;
  torre?: number;
  alicuota?: string;
}): Promise<Unidad> {
  return apiFetch<Unidad>("/api/v1/unidades/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
