jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);

import { enviarAlerta } from "./enviarAlerta";
import * as alertasApi from "../api/alertas";
import * as cola from "./colaEnvio";
import { ErrorDeRed, ErrorDeServidor, SesionExpiradaError } from "../api/client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("si crearAlerta funciona, devuelve la alerta creada", async () => {
  jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 5 } as any);
  const resultado = await enviarAlerta("otro", null, null);
  expect(resultado).toEqual({ id: 5 });
});

test("si crearAlerta falla por un ErrorDeRed (sin señal), encola y devuelve {encolada: true} sin lanzar", async () => {
  jest.spyOn(alertasApi, "crearAlerta").mockRejectedValue(new ErrorDeRed("sin red"));
  const encolarSpy = jest.spyOn(cola, "encolarAlerta").mockResolvedValue();
  const resultado = await enviarAlerta("otro", null, null);
  expect(resultado).toEqual({ encolada: true });
  expect(encolarSpy).toHaveBeenCalled();
});

test("si crearAlerta falla con un ErrorDeServidor (ej. 400), NO encola -- reintentarlo no lo arregla", async () => {
  // Hallazgo I2 de la revisión final: encolar un error no transitorio
  // (un 400/401/403/500 real) convierte a esa alerta en un "poison pill"
  // que bloquea la cola para siempre (ver colaEnvio.ts).
  jest.spyOn(alertasApi, "crearAlerta").mockRejectedValue(new ErrorDeServidor(400));
  const encolarSpy = jest.spyOn(cola, "encolarAlerta").mockResolvedValue();
  await expect(enviarAlerta("otro", null, null)).rejects.toBeInstanceOf(ErrorDeServidor);
  expect(encolarSpy).not.toHaveBeenCalled();
});

test("si crearAlerta falla porque la sesión expiró, tampoco encola -- hay que loguearse de nuevo, no reintentar en silencio", async () => {
  jest.spyOn(alertasApi, "crearAlerta").mockRejectedValue(new SesionExpiradaError("vencida"));
  const encolarSpy = jest.spyOn(cola, "encolarAlerta").mockResolvedValue();
  await expect(enviarAlerta("otro", null, null)).rejects.toBeInstanceOf(SesionExpiradaError);
  expect(encolarSpy).not.toHaveBeenCalled();
});
