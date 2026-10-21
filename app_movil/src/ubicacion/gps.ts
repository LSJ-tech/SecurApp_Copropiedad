import * as Location from "expo-location";

export async function obtenerUbicacionActual(): Promise<{ latitud: number; longitud: number } | null> {
  try {
    const { status } = await Location.requestForegroundPermissionsAsync();
    if (status !== "granted") return null;
    const posicion = await Location.getCurrentPositionAsync();
    return { latitud: posicion.coords.latitude, longitud: posicion.coords.longitude };
  } catch {
    // Nunca bloquea el envío de la alerta por un problema de GPS -- D-04 #1
    // es "automático", no "obligatorio".
    return null;
  }
}
