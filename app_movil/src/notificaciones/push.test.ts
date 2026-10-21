import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { registrarDispositivoPush, configurarManejadorDeNotificaciones, obtenerAlertaIdDeNotificacionFria } from "./push";
import * as dispositivosApi from "../api/dispositivos";

jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
  setNotificationHandler: jest.fn(),
  getLastNotificationResponseAsync: jest.fn(),
}));

afterEach(() => {
  jest.restoreAllMocks();
  jest.clearAllMocks();
});

test("en Web, no pide permiso ni registra nada", async () => {
  Platform.OS = "web";
  const registrarSpy = jest.spyOn(dispositivosApi, "registrarDispositivo").mockResolvedValue();
  await registrarDispositivoPush();
  expect(registrarSpy).not.toHaveBeenCalled();
});

test("en nativo con permiso concedido, registra el token obtenido", async () => {
  Platform.OS = "android";
  (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "undetermined" });
  (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
  (Notifications.getExpoPushTokenAsync as jest.Mock).mockResolvedValue({ data: "ExponentPushToken[abc]" });
  const registrarSpy = jest.spyOn(dispositivosApi, "registrarDispositivo").mockResolvedValue();
  await registrarDispositivoPush();
  expect(registrarSpy).toHaveBeenCalledWith("ExponentPushToken[abc]", "android");
});

test("en nativo con permiso denegado, no registra nada ni lanza", async () => {
  Platform.OS = "ios";
  (Notifications.getPermissionsAsync as jest.Mock).mockResolvedValue({ status: "undetermined" });
  (Notifications.requestPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
  const registrarSpy = jest.spyOn(dispositivosApi, "registrarDispositivo").mockResolvedValue();
  await registrarDispositivoPush();
  expect(registrarSpy).not.toHaveBeenCalled();
});

test("configurarManejadorDeNotificaciones hace que una alerta en primer plano SÍ se muestre", () => {
  // Hallazgo I7 de la revisión final: sin esto, Expo no muestra nada si
  // la notificación llega con la app abierta (comportamiento por
  // defecto es no mostrarla).
  Platform.OS = "android";
  configurarManejadorDeNotificaciones();
  expect(Notifications.setNotificationHandler).toHaveBeenCalledWith(
    expect.objectContaining({ handleNotification: expect.any(Function) })
  );
  const { handleNotification } = (Notifications.setNotificationHandler as jest.Mock).mock.calls[0][0];
  return expect(handleNotification()).resolves.toMatchObject({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
  });
});

test("en Web, configurarManejadorDeNotificaciones no hace nada", () => {
  Platform.OS = "web";
  configurarManejadorDeNotificaciones();
  expect(Notifications.setNotificationHandler).not.toHaveBeenCalled();
});

test("obtenerAlertaIdDeNotificacionFria devuelve el alerta_id si la app se abrió tocando una notificación", async () => {
  // Hallazgo I7: con la app cerrada (lo más común en una emergencia
  // real), solo addNotificationResponseReceivedListener no alcanza --
  // ese evento no se dispara para la notificación que recién abrió la
  // app, hay que preguntarle a getLastNotificationResponseAsync.
  (Notifications.getLastNotificationResponseAsync as jest.Mock).mockResolvedValue({
    notification: { request: { content: { data: { tipo: "alerta", alerta_id: 42 } } } },
  });
  await expect(obtenerAlertaIdDeNotificacionFria()).resolves.toBe(42);
});

test("obtenerAlertaIdDeNotificacionFria devuelve null si la app no se abrió desde una notificación", async () => {
  (Notifications.getLastNotificationResponseAsync as jest.Mock).mockResolvedValue(null);
  await expect(obtenerAlertaIdDeNotificacionFria()).resolves.toBeNull();
});
