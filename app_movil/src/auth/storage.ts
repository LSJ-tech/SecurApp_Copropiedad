import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const CLAVE_ACCESS = "mibarrio.access";
const CLAVE_REFRESH = "mibarrio.refresh";

// expo-secure-store no soporta Web -- ahí se usa localStorage, con la
// misma interfaz async que el resto de la app espera.
async function leer(clave: string): Promise<string | null> {
  if (Platform.OS === "web") {
    return localStorage.getItem(clave);
  }
  return SecureStore.getItemAsync(clave);
}

async function escribir(clave: string, valor: string): Promise<void> {
  if (Platform.OS === "web") {
    localStorage.setItem(clave, valor);
    return;
  }
  await SecureStore.setItemAsync(clave, valor);
}

async function borrar(clave: string): Promise<void> {
  if (Platform.OS === "web") {
    localStorage.removeItem(clave);
    return;
  }
  await SecureStore.deleteItemAsync(clave);
}

export async function guardarTokens(access: string, refresh: string): Promise<void> {
  await escribir(CLAVE_ACCESS, access);
  await escribir(CLAVE_REFRESH, refresh);
}

export async function obtenerTokens(): Promise<{ access: string; refresh: string } | null> {
  const access = await leer(CLAVE_ACCESS);
  const refresh = await leer(CLAVE_REFRESH);
  if (!access || !refresh) return null;
  return { access, refresh };
}

export async function borrarTokens(): Promise<void> {
  await borrar(CLAVE_ACCESS);
  await borrar(CLAVE_REFRESH);
}
