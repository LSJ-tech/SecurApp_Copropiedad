jest.mock("expo-location", () => ({
  requestForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "denied" }),
  getCurrentPositionAsync: jest.fn(),
}));
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);

const mockPush = jest.fn();
jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush }),
}));

const mockUseAuth = jest.fn();
jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

import { act, cleanup, render, fireEvent, screen } from "@testing-library/react-native";
import PantallaPanico from "@/app/(vecino)/index";
import * as enviarAlertaModulo from "@/alertas/enviarAlerta";
import * as donacionesApi from "@/api/donaciones";
import * as alertasApi from "@/api/alertas";
import { ErrorDeServidor } from "@/api/client";

beforeEach(() => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "residente",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan", telefono: "",
    },
  });
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([]);
});

afterEach(async () => {
  await cleanup();
  jest.restoreAllMocks();
  jest.clearAllMocks();
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

test("con donación activa, la tarjeta muestra el monto mensual y el botón navega a Donar", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-09-01T00:00:00Z" },
    pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
  });
  await render(<PantallaPanico />);
  await screen.findByText(/2\.000\/mes/);
  await fireEvent.press(screen.getByText(/ver mi donación/i));
  expect(mockPush).toHaveBeenCalledWith("/donar");
});

test("sin donación activa, la tarjeta invita a donar", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/activa una donación automática/i);
  await fireEvent.press(screen.getByText(/^donar$/i));
  expect(mockPush).toHaveBeenCalledWith("/donar");
});

test("muestra mi unidad con las etiquetas propias del condominio", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "residente",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: { numero: "54", torre_nombre: "9" },
      nombre: "Logan", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  await screen.findByText(/block 9, departamento 54/i);
});

test("sin unidad asignada, muestra el mensaje según el género de la etiqueta", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/sin departamento asignado/i);
});

test("Invitar vecinos navega a la pantalla de invitar", async () => {
  await render(<PantallaPanico />);
  await fireEvent.press(await screen.findByText(/invitar vecinos/i));
  expect(mockPush).toHaveBeenCalledWith("/invitar");
});

test("Directorio no aparece para un residente", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/invitar vecinos/i);
  expect(screen.queryByText(/^directorio$/i)).toBeNull();
});

test("con rol delegado, Directorio navega al directorio", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "delegado",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  await fireEvent.press(await screen.findByText(/^directorio$/i));
  expect(mockPush).toHaveBeenCalledWith("/directorio");
});

test("muestra las alertas activas y cada una navega a su detalle", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([
    { id: 9, tipo_display: "Robo", estado: "activa", estado_display: "Activa" } as any,
  ]);
  await render(<PantallaPanico />);
  await fireEvent.press(await screen.findByText(/robo/i));
  expect(mockPush).toHaveBeenCalledWith("/alertas/9");
});

test("sin alertas activas, muestra 'Sin alertas activas.'", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/sin alertas activas/i);
});

test("si fallan las tarjetas secundarias (donación/alertas), el botón de pánico sigue funcionando", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockRejectedValue(new Error("sin red"));
  jest.spyOn(alertasApi, "listarAlertas").mockRejectedValue(new Error("sin red"));
  const enviarSpy = jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockResolvedValue({ id: 1 } as any);
  await render(<PantallaPanico />);
  jest.useFakeTimers();
  await fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  expect(enviarSpy).toHaveBeenCalled();
});
