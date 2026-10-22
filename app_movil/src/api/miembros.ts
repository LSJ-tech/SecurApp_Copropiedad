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

/** Rutas de DRF ("?page=2") a partir de la URL absoluta que viene en
 * `next` -- apiFetch espera una ruta relativa (le agrega API_BASE_URL
 * él mismo), nunca una URL absoluta. */
function rutaDePagina(urlAbsoluta: string): string {
  const query = urlAbsoluta.split("?")[1];
  return query ? `/api/v1/miembros/?${query}` : "/api/v1/miembros/";
}

export async function listarMiembros(): Promise<Miembro[]> {
  // Hallazgo Important de la revisión final: Empart (cliente real) tiene
  // 56+ membresías -- quedarse solo con la primera página (50) dejaba
  // miembros reales invisibles en la lista.
  const todos: Miembro[] = [];
  let ruta: string | null = "/api/v1/miembros/";
  while (ruta) {
    const pagina = await apiFetch<PaginaDRF<Miembro>>(ruta);
    todos.push(...pagina.results);
    ruta = pagina.next ? rutaDePagina(pagina.next) : null;
  }
  return todos;
}

export function crearMiembro(payload: CrearMiembroPayload): Promise<CrearMiembroResultado> {
  return apiFetch<CrearMiembroResultado>("/api/v1/miembros/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
