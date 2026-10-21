jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);

import AsyncStorage from "@react-native-async-storage/async-storage";
import { encolarAlerta, procesarCola } from "./colaEnvio";
import * as alertasApi from "../api/alertas";

beforeEach(async () => {
  await AsyncStorage.clear();
});

afterEach(() => {
  jest.restoreAllMocks();
});

test("procesa los items encolados en orden y los quita al confirmar exito", async () => {
  await encolarAlerta({ tipo: "otro" });
  await encolarAlerta({ tipo: "incendio" });
  const crearSpy = jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 1 } as any);
  await procesarCola();
  expect(crearSpy.mock.calls.map((c) => c[0].tipo)).toEqual(["otro", "incendio"]);
});

test("si un item falla, se detiene sin saltar al siguiente (no reordena)", async () => {
  await encolarAlerta({ tipo: "otro" });
  await encolarAlerta({ tipo: "incendio" });
  const crearSpy = jest
    .spyOn(alertasApi, "crearAlerta")
    .mockRejectedValueOnce(new Error("sin red"))
    .mockResolvedValueOnce({ id: 2 } as any);
  await procesarCola();
  expect(crearSpy).toHaveBeenCalledTimes(1);
});
