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
