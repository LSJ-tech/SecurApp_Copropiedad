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

/** Rutas de DRF ("?page=2") a partir de la URL absoluta que viene en
 * `next` -- apiFetch espera una ruta relativa (le agrega API_BASE_URL
 * él mismo), nunca una URL absoluta. */
function rutaDePagina(urlAbsoluta: string): string {
  const query = urlAbsoluta.split("?")[1];
  return query ? `/api/v1/unidades/?${query}` : "/api/v1/unidades/";
}

export async function listarUnidades(): Promise<Unidad[]> {
  // Hallazgo Important de la revisión final: Empart (cliente real) tiene
  // 352 unidades -- quedarse solo con la primera página (50) dejaba la
  // mayoría de las torres sin unidades elegibles al crear un miembro.
  const todas: Unidad[] = [];
  let ruta: string | null = "/api/v1/unidades/";
  while (ruta) {
    const pagina = await apiFetch<PaginaDRF<Unidad>>(ruta);
    todas.push(...pagina.results);
    ruta = pagina.next ? rutaDePagina(pagina.next) : null;
  }
  return todas;
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
