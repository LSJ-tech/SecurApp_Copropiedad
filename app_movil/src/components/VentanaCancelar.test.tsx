import { act, cleanup, render, fireEvent, screen } from "@testing-library/react-native";
import { VentanaCancelar } from "./VentanaCancelar";
import * as alertasApi from "../api/alertas";

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

test("el boton desaparece despues de 10 segundos", async () => {
  jest.useFakeTimers();
  await render(<VentanaCancelar alertaId={9} onCancelada={jest.fn()} />);
  await act(async () => {
    await jest.advanceTimersByTimeAsync(10000);
  });
  jest.useRealTimers();
  expect(screen.queryByText(/Cancelar, fue un error/i)).toBeNull();
});
