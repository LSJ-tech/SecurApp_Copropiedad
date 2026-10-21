import * as Location from "expo-location";
import { obtenerUbicacionActual } from "./gps";

jest.mock("expo-location");

afterEach(() => {
  jest.restoreAllMocks();
});

test("con permiso concedido, devuelve latitud/longitud", async () => {
  (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ status: "granted" });
  (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue({
    coords: { latitude: -33.45, longitude: -70.65 },
  });
  expect(await obtenerUbicacionActual()).toEqual({ latitud: -33.45, longitud: -70.65 });
});

test("con permiso denegado, devuelve null sin lanzar", async () => {
  (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({ status: "denied" });
  await expect(obtenerUbicacionActual()).resolves.toBeNull();
});

test("si el dialogo de permiso o el GPS tardan mas de 2s, devuelve null en vez de bloquear el envio", async () => {
  // Hallazgo C4 de la revision final: D-04 #1 dice "sin ningun paso
  // extra visible" -- un dialogo de permiso pendiente o un GPS en frio
  // (10-30s+) no puede demorar el POST de la alerta.
  jest.useFakeTimers();
  (Location.requestForegroundPermissionsAsync as jest.Mock).mockImplementation(
    () => new Promise(() => {}) // nunca se resuelve -- simula el dialogo pendiente
  );
  const promesa = expect(obtenerUbicacionActual()).resolves.toBeNull();
  await jest.advanceTimersByTimeAsync(2000);
  await promesa;
  jest.useRealTimers();
});
