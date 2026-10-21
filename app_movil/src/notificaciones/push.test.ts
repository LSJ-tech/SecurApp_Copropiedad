import { Platform } from "react-native";
import * as Notifications from "expo-notifications";
import { registrarDispositivoPush } from "./push";
import * as dispositivosApi from "../api/dispositivos";

jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
}));

afterEach(() => {
  jest.restoreAllMocks();
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
  await expect(registrarDispositivoPush()).resolves.not.toThrow();
  expect(registrarSpy).not.toHaveBeenCalled();
});
