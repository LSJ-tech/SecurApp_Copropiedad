import { ErrorDeServidor } from "./client";

/** Primer mensaje real de validación de un ErrorDeServidor.body (shape
 * de DRF: {campo: [mensajes]}) -- usado por todo formulario que
 * necesite mostrar el error real del backend en vez de uno genérico.
 * Compartido entre Mi perfil, Mi condominio, Torres y Unidades. */
export function primerMensajeDeError(error: unknown): string {
  if (error instanceof ErrorDeServidor && error.body && typeof error.body === "object") {
    const primero = Object.values(error.body as Record<string, unknown>)[0];
    if (Array.isArray(primero) && typeof primero[0] === "string") return primero[0];
  }
  return "No se pudo guardar. Probá de nuevo.";
}

/** Mensaje de un ErrorDeServidor.body con shape {"detail": "..."} -- el
 * que usan los endpoints que no son un form de Django (LogoutView,
 * DevquadEntrarCondominioApiView, pagos/api_views.py, etc.), distinto
 * del shape {campo: [mensajes]} que espera primerMensajeDeError. */
export function mensajeDetalleDeError(error: unknown, porDefecto: string): string {
  if (error instanceof ErrorDeServidor && error.body && typeof error.body === "object") {
    const detalle = (error.body as Record<string, unknown>).detail;
    if (typeof detalle === "string") return detalle;
  }
  return porDefecto;
}
