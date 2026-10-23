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

/** Sin esto, Expo no muestra nada si la notificación llega con la app
 * abierta (hallazgo I7 de la revisión final) -- se llama una vez al
 * arrancar la app. */
export function configurarManejadorDeNotificaciones(): void {
  if (Platform.OS === "web") return;
  Notifications.setNotificationHandler({
    // El tipo de handleNotification exige devolver una Promise -- sin
    // await real adentro, Promise.resolve() cumple el tipo sin el
    // `async` que Sonar marca como innecesario (S7503).
    handleNotification: () =>
      Promise.resolve({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
  });
}

/** Con la app cerrada (el caso más común en una emergencia real),
 * addNotificationResponseReceivedListener no alcanza -- ese evento no
 * se dispara para la notificación que recién abrió la app (hallazgo I7
 * de la revisión final). getLastNotificationResponse (sin "Async") es
 * el reemplazo no deprecado -- ya es síncrono, getLastNotificationResponseAsync
 * solo envolvía el mismo valor en una Promise. */
export function obtenerAlertaIdDeNotificacionFria(): number | null {
  const respuesta = Notifications.getLastNotificationResponse();
  const alertaId = respuesta?.notification.request.content.data?.alerta_id;
  return typeof alertaId === "number" ? alertaId : null;
}
