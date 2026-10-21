import { Platform } from "react-native";
import * as Notifications from "expo-notifications";

import { registrarDispositivo } from "../api/dispositivos";

export async function registrarDispositivoPush(): Promise<void> {
  // Confirmado con el usuario: el push de esta app queda acotado a
  // celular -- Expo for Web no integra Web Push/VAPID (eso sigue siendo
  // exclusivo de la PWA).
  if (Platform.OS === "web") return;

  const permisoActual = await Notifications.getPermissionsAsync();
  let estado = permisoActual.status;
  if (estado !== "granted") {
    const solicitado = await Notifications.requestPermissionsAsync();
    estado = solicitado.status;
  }
  if (estado !== "granted") return;

  const { data: token } = await Notifications.getExpoPushTokenAsync();
  await registrarDispositivo(token, Platform.OS as "ios" | "android");
}
