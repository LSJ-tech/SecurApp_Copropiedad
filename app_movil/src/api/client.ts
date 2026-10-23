import { borrarTokens, guardarTokens, obtenerTokens } from "../auth/storage";

export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "";

const TIMEOUT_MS = 8000;

export class SesionExpiradaError extends Error {
  sesionExpirada = true as const;
}

/** fetch() mismo no respondió (sin red, timeout) -- transitorio, seguro
 * de reintentar/encolar. */
export class ErrorDeRed extends Error {}

/** El servidor SÍ respondió, pero con un error (4xx/5xx) -- no es
 * transitorio, reintentarlo a ciegas no lo va a arreglar. */
export class ErrorDeServidor extends Error {
  constructor(public status: number, public body?: unknown) {
    super(`El servidor respondió ${status}.`);
  }
}

async function leerCuerpoSiSePuede(respuesta: Response): Promise<unknown> {
  return respuesta.json().catch(() => undefined);
}

type ListenerSesionExpirada = () => void;
let listenerSesionExpirada: ListenerSesionExpirada | null = null;

/** Único listener a la vez -- lo arma AuthContext al montar. Pasar
 * `null` lo saca (usado en tests para no filtrar estado entre casos). */
export function alSesionExpirada(listener: ListenerSesionExpirada | null): void {
  listenerSesionExpirada = listener;
}

async function fetchConTimeout(path: string, options: RequestInit): Promise<Response> {
  const controlador = new AbortController();
  const temporizador = setTimeout(() => controlador.abort(), TIMEOUT_MS);
  try {
    return await fetch(`${API_BASE_URL}${path}`, { ...options, signal: controlador.signal });
  } catch (error) {
    throw new ErrorDeRed(error instanceof Error ? error.message : "fallo de red");
  } finally {
    clearTimeout(temporizador);
  }
}

// Single-flight: si dos requests reciben 401 al mismo tiempo, solo una
// refresca de verdad -- la segunda espera esa misma promesa en vez de
// gastar el refresh (que con ROTATE_REFRESH_TOKENS+BLACKLIST_AFTER_ROTATION
// ya quedó usado) una segunda vez.
let refrescoEnVuelo: Promise<{ access: string; refresh: string } | null> | null = null;

async function refrescarTokens(refresh: string): Promise<{ access: string; refresh: string } | null> {
  refrescoEnVuelo ??= (async () => {
    try {
      const respuesta = await fetchConTimeout("/api/v1/auth/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh }),
      });
      if (!respuesta.ok) return null;
      const datos = await respuesta.json();
      // El backend rota el refresh en cada uso (ROTATE_REFRESH_TOKENS +
      // BLACKLIST_AFTER_ROTATION, config/settings.py) -- el que vino en
      // esta respuesta es el único que sigue siendo válido.
      return { access: datos.access as string, refresh: datos.refresh as string };
    } finally {
      refrescoEnVuelo = null;
    }
  })();
  return refrescoEnVuelo;
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
    const respuesta = await fetchConTimeout(path, { ...options, headers });
    if (!respuesta.ok) throw new ErrorDeServidor(respuesta.status, await leerCuerpoSiSePuede(respuesta));
    return respuesta.json();
  }

  const tokens = await obtenerTokens();
  if (tokens) headers.Authorization = `Bearer ${tokens.access}`;

  let respuesta = await fetchConTimeout(path, { ...options, headers });

  if (respuesta.status === 401 && tokens) {
    const nuevos = await refrescarTokens(tokens.refresh);
    if (!nuevos) {
      await borrarTokens();
      listenerSesionExpirada?.();
      throw new SesionExpiradaError("La sesión expiró, hay que iniciar sesión de nuevo.");
    }
    await guardarTokens(nuevos.access, nuevos.refresh);
    respuesta = await fetchConTimeout(path, {
      ...options,
      headers: { ...headers, Authorization: `Bearer ${nuevos.access}` },
    });
  }

  if (!respuesta.ok) throw new ErrorDeServidor(respuesta.status, await leerCuerpoSiSePuede(respuesta));
  return respuesta.json();
}
