import * as Location from "expo-location";

const TIMEOUT_MS = 2000;

function conLimite<T>(promesa: Promise<T>): Promise<T | null> {
  return new Promise((resolve) => {
    const temporizador = setTimeout(() => resolve(null), TIMEOUT_MS);
    promesa.then(
      (valor) => {
        clearTimeout(temporizador);
        resolve(valor);
      },
      () => {
        clearTimeout(temporizador);
        resolve(null);
      }
    );
  });
}

export async function obtenerUbicacionActual(): Promise<{ latitud: number; longitud: number } | null> {
  // D-04 #1: "sin ningún paso extra visible" -- un diálogo de permiso
  // pendiente o un GPS en frío (10-30s+) nunca puede demorar el envío
  // real de la alerta (hallazgo C4 de la revisión final).
  const permiso = await conLimite(Location.requestForegroundPermissionsAsync());
  if (permiso?.status !== "granted") return null;

  const posicion = await conLimite(Location.getCurrentPositionAsync());
  if (!posicion) return null;
  return { latitud: posicion.coords.latitude, longitud: posicion.coords.longitude };
}
