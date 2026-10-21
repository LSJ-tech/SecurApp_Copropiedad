import { borrarTokens, guardarTokens, obtenerTokens } from "../auth/storage";

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "";

class SesionExpiradaError extends Error {
  sesionExpirada = true as const;
}

async function refrescarAccessToken(refresh: string): Promise<string | null> {
  const respuesta = await fetch(`${API_BASE_URL}/api/v1/auth/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!respuesta.ok) return null;
  const datos = await respuesta.json();
  return datos.access as string;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  requiereAuth: boolean = true
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (!requiereAuth) {
    const respuesta = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
    if (!respuesta.ok) {
      throw new Error(`apiFetch sin auth falló: ${respuesta.status}`);
    }
    return respuesta.json();
  }

  const tokens = await obtenerTokens();
  if (tokens) headers.Authorization = `Bearer ${tokens.access}`;

  let respuesta = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });

  if (respuesta.status === 401 && tokens) {
    const nuevoAccess = await refrescarAccessToken(tokens.refresh);
    if (!nuevoAccess) {
      await borrarTokens();
      throw new SesionExpiradaError("La sesión expiró, hay que iniciar sesión de nuevo.");
    }
    await guardarTokens(nuevoAccess, tokens.refresh);
    respuesta = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: { ...headers, Authorization: `Bearer ${nuevoAccess}` },
    });
  }

  if (!respuesta.ok) {
    throw new Error(`apiFetch falló: ${respuesta.status}`);
  }
  return respuesta.json();
}
