import { apiFetch } from "./client";

export type MembresiaOut = {
  rol: string;
  condominio: { id: number; nombre: string; [k: string]: unknown };
  unidad: { numero: string; [k: string]: unknown } | null;
  nombre: string;
  telefono: string;
};

export type LoginOut = {
  access: string;
  refresh: string;
  membresia: MembresiaOut | null;
};

export function login(username: string, password: string): Promise<LoginOut> {
  return apiFetch<LoginOut>(
    "/api/v1/auth/login/",
    { method: "POST", body: JSON.stringify({ username, password }) },
    false
  );
}

/** Confirma quién es el usuario de los tokens guardados -- el backend
 * da 409 si no tiene Membresia (cuenta devquad, ver MeView). */
export function obtenerMiPerfil(): Promise<MembresiaOut> {
  return apiFetch<MembresiaOut>("/api/v1/auth/me/");
}

/** Pone el refresh en la lista negra del servidor -- sin esto, cerrar
 * sesión solo borraba los tokens localmente (hallazgo de la revisión
 * final): un teléfono perdido después de un "logout" seguía pudiendo
 * refrescar la sesión hasta por 30 días (REFRESH_TOKEN_LIFETIME). */
export function logout(refresh: string): Promise<void> {
  return apiFetch<void>("/api/v1/auth/logout/", {
    method: "POST",
    body: JSON.stringify({ refresh }),
  });
}
