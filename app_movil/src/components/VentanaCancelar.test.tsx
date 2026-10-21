import { act, cleanup, render, fireEvent, screen } from "@testing-library/react-native";
import { VentanaCancelar } from "./VentanaCancelar";
import * as alertasApi from "../api/alertas";
import { ErrorDeRed } from "../api/client";

afterEach(async () => {
  await cleanup();
  jest.restoreAllMocks();
});

test("tocar Cancelar dentro de la ventana llama a resolverAlerta con falsa_alarma", async () => {
  const resolverSpy = jest.spyOn(alertasApi, "resolverAlerta").mockResolvedValue({} as any);
  const onCancelada = jest.fn();
  await render(<VentanaCancelar alertaId={9} onCancelada={onCancelada} />);
  await fireEvent.press(screen.getByText(/Cancelar, fue un error/i));
  await Promise.resolve();
  expect(resolverSpy).toHaveBeenCalledWith(9, "falsa_alarma");
  expect(onCancelada).toHaveBeenCalled();
});

test("si resolverAlerta falla (ej. sin señal), muestra un error en vez de quedar en un rechazo sin manejar", async () => {
  // Hallazgo I5 de la revisión final.
  jest.spyOn(alertasApi, "resolverAlerta").mockRejectedValue(new ErrorDeRed("sin red"));
  const onCancelada = jest.fn();
  await render(<VentanaCancelar alertaId={9} onCancelada={onCancelada} />);
  await fireEvent.press(screen.getByText(/Cancelar, fue un error/i));
  await screen.findByText(/no se pudo cancelar/i);
  expect(onCancelada).not.toHaveBeenCalled();
});

test("tocar Cancelar dos veces seguidas no manda dos PATCH", async () => {
  // Hallazgo I5: sin una guarda, varios toques mientras la primera
  // request sigue en vuelo mandaban varios PATCH.
  let resolverPrimera: (valor: any) => void = () => {};
  const esperaPrimera = new Promise((resolve) => {
    resolverPrimera = resolve;
  });
  const resolverSpy = jest.spyOn(alertasApi, "resolverAlerta").mockReturnValue(esperaPrimera as any);
  await render(<VentanaCancelar alertaId={9} onCancelada={jest.fn()} />);
  const boton = screen.getByText(/Cancelar, fue un error/i);
  // Ninguna de las dos se espera antes de la otra -- el handler de la
  // primera sigue colgado en el resolverAlerta pendiente, así que
  // esperarla antes de disparar la segunda nunca llegaría a probar nada.
  const primeraPromesa = fireEvent.press(boton);
  const segundaPromesa = fireEvent.press(boton);
  await act(async () => {
    resolverPrimera({});
    await Promise.all([primeraPromesa, segundaPromesa]);
  });
  expect(resolverSpy).toHaveBeenCalledTimes(1);
});

test("el boton desaparece despues de 10 segundos", async () => {
  jest.useFakeTimers();
  await render(<VentanaCancelar alertaId={9} onCancelada={jest.fn()} />);
  await act(async () => {
    await jest.advanceTimersByTimeAsync(10000);
  });
  jest.useRealTimers();
  expect(screen.queryByText(/Cancelar, fue un error/i)).toBeNull();
});
