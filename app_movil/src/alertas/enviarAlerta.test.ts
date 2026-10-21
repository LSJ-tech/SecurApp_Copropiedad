jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);

import { enviarAlerta } from "./enviarAlerta";
import * as alertasApi from "../api/alertas";
import * as cola from "./colaEnvio";

afterEach(() => {
  jest.restoreAllMocks();
});

test("si crearAlerta funciona, devuelve la alerta creada", async () => {
  jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 5 } as any);
  const resultado = await enviarAlerta("otro", null, null);
  expect(resultado).toEqual({ id: 5 });
});

test("si crearAlerta falla, encola y devuelve {encolada: true} sin lanzar", async () => {
  jest.spyOn(alertasApi, "crearAlerta").mockRejectedValue(new Error("sin red"));
  const encolarSpy = jest.spyOn(cola, "encolarAlerta").mockResolvedValue();
  const resultado = await enviarAlerta("otro", null, null);
  expect(resultado).toEqual({ encolada: true });
  expect(encolarSpy).toHaveBeenCalled();
});
