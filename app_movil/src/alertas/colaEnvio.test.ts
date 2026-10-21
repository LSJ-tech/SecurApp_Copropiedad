jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);

import { AppState } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { encolarAlerta, procesarCola, iniciarProcesamientoAutomatico } from "./colaEnvio";
import * as alertasApi from "../api/alertas";
import { ErrorDeRed, ErrorDeServidor, SesionExpiradaError } from "../api/client";

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

test("ante un ErrorDeRed (transitorio), se detiene sin saltar al siguiente ni descartar nada (no reordena)", async () => {
  await encolarAlerta({ tipo: "otro" });
  await encolarAlerta({ tipo: "incendio" });
  const crearSpy = jest
    .spyOn(alertasApi, "crearAlerta")
    .mockRejectedValueOnce(new ErrorDeRed("sin red"))
    .mockResolvedValueOnce({ id: 2 } as any);
  await procesarCola();
  expect(crearSpy).toHaveBeenCalledTimes(1);
  // Hallazgo I3 de la revisión final: el test original no confirmaba que
  // los 2 items siguieran en la cola -- solo que crearAlerta no se
  // hubiera llamado una segunda vez (lo cual también pasaría si, por
  // error, se hubiera vaciado la cola entera).
  const cola = JSON.parse((await AsyncStorage.getItem("mibarrio.colaAlertas")) ?? "[]");
  expect(cola).toEqual([{ tipo: "otro" }, { tipo: "incendio" }]);
});

test("ante un ErrorDeServidor (no transitorio, ej. 400), descarta ESE item y sigue con el resto -- no lo bloquea para siempre", async () => {
  // Hallazgo I2: un 400/401/403/500 real no se arregla reintentando.
  // Tratarlo igual que un fallo de red convertía ese item en un
  // "poison pill" que bloqueaba la cola entera para siempre.
  await encolarAlerta({ tipo: "otro" });
  await encolarAlerta({ tipo: "incendio" });
  const crearSpy = jest
    .spyOn(alertasApi, "crearAlerta")
    .mockRejectedValueOnce(new ErrorDeServidor(400))
    .mockResolvedValueOnce({ id: 2 } as any);
  await procesarCola();
  expect(crearSpy).toHaveBeenCalledTimes(2);
  const cola = JSON.parse((await AsyncStorage.getItem("mibarrio.colaAlertas")) ?? "[]");
  expect(cola).toEqual([]);
});

test("si la sesión expiró a mitad de la cola, se detiene sin descartar nada -- no es culpa de la alerta", async () => {
  await encolarAlerta({ tipo: "otro" });
  const crearSpy = jest.spyOn(alertasApi, "crearAlerta").mockRejectedValue(new SesionExpiradaError("vencida"));
  await procesarCola();
  expect(crearSpy).toHaveBeenCalledTimes(1);
  const cola = JSON.parse((await AsyncStorage.getItem("mibarrio.colaAlertas")) ?? "[]");
  expect(cola).toEqual([{ tipo: "otro" }]);
});

test("encolar mientras procesarCola está a mitad de camino no pierde el item nuevo", async () => {
  // Hallazgo I3(c): procesarCola tomaba una sola foto de la cola al
  // empezar: si encolarAlerta agregaba algo mientras tanto, el resto
  // que procesarCola escribía al final pisaba ese item nuevo.
  await encolarAlerta({ tipo: "otro" });
  let resolverPrimeraLlamada: () => void = () => {};
  const esperaPrimeraLlamada = new Promise<void>((resolve) => {
    resolverPrimeraLlamada = resolve;
  });
  let llamadas = 0;
  jest.spyOn(alertasApi, "crearAlerta").mockImplementation(async () => {
    llamadas += 1;
    resolverPrimeraLlamada();
    // Le da tiempo a encolarAlerta() de correr mientras procesarCola
    // sigue "en el medio" de procesar el primer item.
    await new Promise((r) => setTimeout(r, 10));
    if (llamadas > 1) throw new ErrorDeRed("sin red");
    return { id: 1 } as any;
  });
  const promesaProcesar = procesarCola();
  await esperaPrimeraLlamada;
  await encolarAlerta({ tipo: "incendio" });
  await promesaProcesar;
  const cola = JSON.parse((await AsyncStorage.getItem("mibarrio.colaAlertas")) ?? "[]");
  expect(cola).toEqual([{ tipo: "incendio" }]);
});

test("dos llamadas a procesarCola en simultáneo no duplican el envío", async () => {
  await encolarAlerta({ tipo: "otro" });
  const crearSpy = jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 1 } as any);
  await Promise.all([procesarCola(), procesarCola()]);
  expect(crearSpy).toHaveBeenCalledTimes(1);
});

describe("iniciarProcesamientoAutomatico", () => {
  // Hallazgo C1 de la revisión final: colaEnvio.ts nunca se conectaba a
  // nada -- ninguna alerta encolada se reintentaba jamás, sin señal o
  // con ella de vuelta.

  test("procesa la cola una vez de entrada al llamarse", async () => {
    await encolarAlerta({ tipo: "otro" });
    const crearSpy = jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 1 } as any);
    const detener = iniciarProcesamientoAutomatico();
    await new Promise((r) => setTimeout(r, 0));
    expect(crearSpy).toHaveBeenCalledTimes(1);
    detener();
  });

  test("reprocesa la cola cuando la app vuelve a primer plano", async () => {
    let callback: ((estado: string) => void) | null = null;
    jest.spyOn(AppState, "addEventListener").mockImplementation((_evento, cb) => {
      callback = cb as (estado: string) => void;
      return { remove: jest.fn() } as any;
    });
    const detener = iniciarProcesamientoAutomatico();
    await encolarAlerta({ tipo: "otro" });
    const crearSpy = jest.spyOn(alertasApi, "crearAlerta").mockResolvedValue({ id: 1 } as any);
    callback!("active");
    await new Promise((r) => setTimeout(r, 0));
    expect(crearSpy).toHaveBeenCalledTimes(1);
    detener();
  });

  test("detener() deja de escuchar los cambios de AppState", async () => {
    const removeSpy = jest.fn();
    const addSpy = jest
      .spyOn(AppState, "addEventListener")
      .mockReturnValue({ remove: removeSpy } as any);
    const detener = iniciarProcesamientoAutomatico();
    expect(addSpy).toHaveBeenCalledWith("change", expect.any(Function));
    detener();
    expect(removeSpy).toHaveBeenCalled();
  });
});
