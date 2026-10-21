jest.mock("expo-location", () => ({
  requestForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "denied" }),
  getCurrentPositionAsync: jest.fn(),
}));
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);

import { act, cleanup, render, fireEvent, screen } from "@testing-library/react-native";
import PantallaPanico from "@/app/(vecino)/index";
import * as enviarAlertaModulo from "@/alertas/enviarAlerta";
import { ErrorDeServidor } from "@/api/client";

afterEach(async () => {
  await cleanup();
  jest.restoreAllMocks();
});

test("mientras un envio esta en curso, un segundo press mantenido no dispara una segunda alerta", async () => {
  // Hallazgo I9 de la revision final: sin una guarda, el GPS+POST
  // tardando le daban tiempo al usuario a volver a mantener presionado
  // y mandar una alerta real duplicada.
  let resolverEnvio: (valor: any) => void = () => {};
  const esperaEnvio = new Promise((resolve) => {
    resolverEnvio = resolve;
  });
  const enviarSpy = jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockReturnValue(esperaEnvio as any);

  await render(<PantallaPanico />);
  jest.useFakeTimers();
  const boton = screen.getByTestId("boton-panico");
  await fireEvent(boton, "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  await fireEvent(boton, "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  await act(async () => {
    resolverEnvio({ id: 1 });
    await Promise.resolve();
  });

  expect(enviarSpy).toHaveBeenCalledTimes(1);
});

test("si el envio falla con un error no transitorio, se muestra un mensaje de error visible", async () => {
  jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockRejectedValue(new ErrorDeServidor(400));
  await render(<PantallaPanico />);
  jest.useFakeTimers();
  await fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  await screen.findByText(/no se pudo mandar la alerta/i);
});

test("al mandar una segunda alerta, la ventana de cancelar vuelve a aparecer (no queda pegada a la anterior)", async () => {
  // Hallazgo I4 de la revision final: sin key={alertaEnviadaId}, la
  // segunda VentanaCancelar reusaba la instancia de la primera -- si ya
  // habian pasado los 10s, el boton "Cancelar" no volvia a aparecer.
  jest
    .spyOn(enviarAlertaModulo, "enviarAlerta")
    .mockResolvedValueOnce({ id: 1 } as any)
    .mockResolvedValueOnce({ id: 2 } as any);
  await render(<PantallaPanico />);
  const boton = screen.getByTestId("boton-panico");

  jest.useFakeTimers();
  await fireEvent(boton, "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  await screen.findByText(/cancelar, fue un error/i);
  // Deja pasar los 10s de la primera ventana -- el boton desaparece.
  await act(async () => {
    await jest.advanceTimersByTimeAsync(10000);
  });
  expect(screen.queryByText(/cancelar, fue un error/i)).toBeNull();

  await fireEvent(boton, "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  await screen.findByText(/cancelar, fue un error/i);
});
