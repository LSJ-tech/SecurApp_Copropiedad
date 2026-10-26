jest.mock("expo-location", () => ({
  requestForegroundPermissionsAsync: jest.fn().mockResolvedValue({ status: "denied" }),
  getCurrentPositionAsync: jest.fn(),
}));
jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock")
);

const mockPush = jest.fn();
let mockFocusCallback: (() => void) | null = null;
// require, no import -- jest.mock() está hoisteado arriba de los imports
// del archivo. Diferir a un useEffect de verdad (en vez de llamar el
// callback sincrónicamente durante el render) evita un setState-durante-
// el-render que entraba en loop infinito ("Too many re-renders").
const mockUseFocusEffect = jest.fn((callback: () => void) => {
  mockFocusCallback = callback;
  require("react").useEffect(callback, []);
});
jest.mock("expo-router", () => ({
  useRouter: () => ({ push: mockPush }),
  useFocusEffect: (callback: () => void) => mockUseFocusEffect(callback),
}));

const mockUseAuth = jest.fn();
jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => mockUseAuth(),
}));

import { act, cleanup, render, fireEvent, screen, within } from "@testing-library/react-native";
import PantallaPanico from "@/app/(vecino)/index";
import * as enviarAlertaModulo from "@/alertas/enviarAlerta";
import * as colaEnvioModulo from "@/alertas/colaEnvio";
import * as donacionesApi from "@/api/donaciones";
import * as alertasApi from "@/api/alertas";
import { ErrorDeServidor } from "@/api/client";
import { colores } from "@/theme/colores";

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
  const tarjetaAlertas = await screen.findByTestId("tarjeta-alertas");
  await fireEvent.press(await within(tarjetaAlertas).findByText(/robo/i));
  expect(mockPush).toHaveBeenCalledWith("/alertas/9");
});

test("sin alertas activas, muestra el estado vacío ilustrado", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/todo tranquilo por ahora/i);
});

test("saluda por el nombre de pila del residente", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/hola, logan/i);
});

test("si no hay first_name, usa la primera palabra de nombre", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "residente",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan Silva Jara", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  await screen.findByText(/hola, logan\b/i);
  expect(screen.queryByText(/silva/i)).toBeNull();
});

test("mientras la membresía no cargó, no muestra un saludo roto", async () => {
  mockUseAuth.mockReturnValue({ membresia: null });
  await render(<PantallaPanico />);
  expect(screen.queryByText(/hola,/i)).toBeNull();
});

test("cuando una alerta en cola finalmente se manda, avisa aunque ya haya pasado la confirmación inicial", async () => {
  // Continuación del hallazgo anterior: el autor está excluido de su
  // propio push (notificar_alerta), así que sin este listener nadie le
  // avisa si esa alerta en cola terminó mandándose de verdad.
  let listenerCapturado: ((evento: { tipo: string }) => void) | null = null;
  jest.spyOn(colaEnvioModulo, "alProcesarColaAlerta").mockImplementation((listener: any) => {
    listenerCapturado = listener;
  });
  await render(<PantallaPanico />);
  await act(async () => {
    listenerCapturado?.({ tipo: "enviada" });
  });
  await screen.findByText("Alerta enviada");
  await screen.findByText("Vecinos notificados");
});

test("si una alerta en cola se descarta (error no transitorio), avisa con un error", async () => {
  let listenerCapturado: ((evento: { tipo: string }) => void) | null = null;
  jest.spyOn(colaEnvioModulo, "alProcesarColaAlerta").mockImplementation((listener: any) => {
    listenerCapturado = listener;
  });
  await render(<PantallaPanico />);
  await act(async () => {
    listenerCapturado?.({ tipo: "descartada" });
  });
  await screen.findByText(/no se pudo mandar la alerta que había quedado en cola/i);
});

test("sin conexión, la alerta queda encolada y el residente lo ve -- no queda sin ninguna señal", async () => {
  // Hallazgo real: enviarAlerta() devuelve {encolada: true} (sin id)
  // cuando no hay red -- antes manejarConfirmar solo reaccionaba a un
  // resultado con id, así que un vecino con mala señal mandaba la
  // alerta y no veía absolutamente nada, ni confirmación ni error.
  jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockResolvedValue({ encolada: true } as any);
  await render(<PantallaPanico />);
  jest.useFakeTimers();
  const boton = screen.getByTestId("boton-panico");
  await fireEvent(boton, "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  await screen.findByText("Alerta en cola");
  await screen.findByText("Se enviará apenas vuelva la señal");
});

test("al confirmar el envío, aparece la confirmación animada", async () => {
  jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockResolvedValue({ id: 1 } as any);
  await render(<PantallaPanico />);
  jest.useFakeTimers();
  const boton = screen.getByTestId("boton-panico");
  await fireEvent(boton, "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  await screen.findByText("Alerta enviada");
  await screen.findByText("Vecinos notificados");
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

test("con una donación cancelada, la tarjeta invita a donar en vez de mostrar 'activa'", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: { estado: "cancelada", monto: "2000.00", fecha_creacion: "2026-09-01T00:00:00Z" },
    pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
  });
  await render(<PantallaPanico />);
  await screen.findByText(/activa una donación automática/i);
  expect(screen.queryByText(/donación automática activa/i)).toBeNull();
});

test("al volver a enfocar la pantalla, recarga la donación y las alertas", async () => {
  jest
    .spyOn(donacionesApi, "obtenerMiDonacion")
    .mockResolvedValueOnce({ donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0 })
    .mockResolvedValueOnce({
      donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-09-01T00:00:00Z" },
      pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
    });
  await render(<PantallaPanico />);
  await screen.findByText(/activa una donación automática/i);
  await act(async () => {
    mockFocusCallback?.();
    await Promise.resolve();
  });
  await screen.findByText(/donación automática activa/i);
});

test("al mandar una alerta propia, la tarjeta de alertas activas se actualiza", async () => {
  jest
    .spyOn(alertasApi, "listarAlertas")
    .mockResolvedValueOnce([])
    .mockResolvedValueOnce([{ id: 5, tipo_display: "Robo", estado: "activa", estado_display: "Activa" } as any]);
  jest.spyOn(enviarAlertaModulo, "enviarAlerta").mockResolvedValue({ id: 5 } as any);
  await render(<PantallaPanico />);
  await screen.findByText(/todo tranquilo por ahora/i);
  jest.useFakeTimers();
  await fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(2000);
  });
  jest.useRealTimers();
  const tarjetaAlertas = await screen.findByTestId("tarjeta-alertas");
  await within(tarjetaAlertas).findByText(/robo/i);
});

test("si falla cargar las alertas activas, muestra un error en vez del estado vacío", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockRejectedValue(new Error("sin red"));
  await render(<PantallaPanico />);
  await screen.findByText(/no se pudieron cargar las alertas/i);
  expect(screen.queryByText(/todo tranquilo por ahora/i)).toBeNull();
});

test("el orden de la pantalla es: mi depto, donación, botón de pánico, alertas activas, invitar", async () => {
  await render(<PantallaPanico />);
  await screen.findByText(/invitar vecinos/i);
  const texto = JSON.stringify(screen.toJSON());
  const posiciones = [
    texto.indexOf("Mi departamento"),
    texto.indexOf("Apoya el proyecto"),
    texto.indexOf("Mantén presionado"),
    texto.indexOf("Alertas activas"),
    texto.indexOf("Invitar vecinos"),
  ];
  expect(posiciones).toEqual([...posiciones].sort((a, b) => a - b));
});

test("el botón de pánico y el selector de tipo quedan juntos, sin otra tarjeta en el medio -- el botón primero para que quede visible sin scroll", async () => {
  // Hallazgo de la revisión: con el selector antes, la grilla de 12
  // tipos (ahora siempre visible, ver SelectorTipoAlerta) empujaba el
  // botón de pánico fuera de la vista inicial en una pantalla chica.
  await render(<PantallaPanico />);
  await screen.findByText(/invitar vecinos/i);
  const texto = JSON.stringify(screen.toJSON());
  const posBoton = texto.indexOf("Mantén presionado");
  const posSelector = texto.indexOf("Tipo de emergencia");
  const posAlertas = texto.indexOf("Alertas activas");
  expect(posBoton).toBeLessThan(posSelector);
  expect(posSelector).toBeLessThan(posAlertas);
});

test("la tarjeta de mi depto usa el color de fondo informativo", async () => {
  await render(<PantallaPanico />);
  const tarjeta = await screen.findByTestId("tarjeta-depto");
  expect(tarjeta.props.style).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })]));
});

test("la tarjeta de donación usa el color de fondo de apoyo", async () => {
  await render(<PantallaPanico />);
  const tarjeta = await screen.findByTestId("tarjeta-donacion");
  expect(tarjeta.props.style).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoApoyo })]));
});

test("la tarjeta de invitar vecinos usa el color de apoyo y la de directorio el informativo", async () => {
  mockUseAuth.mockReturnValue({
    membresia: {
      rol: "delegado",
      condominio: { id: 1, nombre: "Empart", etiqueta_torre: "Block", etiqueta_unidad: "Departamento", genero_unidad: "m" },
      unidad: null,
      nombre: "Logan", telefono: "",
    },
  });
  await render(<PantallaPanico />);
  const tarjetaInvitar = await screen.findByTestId("tarjeta-invitar");
  const tarjetaDirectorio = await screen.findByTestId("tarjeta-directorio");
  expect(tarjetaInvitar.props.style).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoApoyo })]));
  expect(tarjetaDirectorio.props.style).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })]));
});

test("sin alertas activas, la tarjeta usa el color positivo", async () => {
  await render(<PantallaPanico />);
  const tarjeta = await screen.findByTestId("tarjeta-alertas");
  expect(tarjeta.props.style).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoPositivo })]));
});

test("con alertas activas reales, la tarjeta usa el color de peligro", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([
    { id: 9, tipo_display: "Robo", estado: "activa", estado_display: "Activa" } as any,
  ]);
  await render(<PantallaPanico />);
  const tarjeta = await screen.findByTestId("tarjeta-alertas");
  expect(tarjeta.props.style).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoPeligro })]));
});

test("si falla cargar las alertas, la tarjeta NO queda verde (no debe parecer 'todo bien')", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockRejectedValue(new Error("sin red"));
  await render(<PantallaPanico />);
  await screen.findByText(/no se pudieron cargar las alertas/i);
  const tarjeta = screen.getByTestId("tarjeta-alertas");
  expect(tarjeta.props.style).not.toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoPositivo })]));
});

test("el botón de pánico no se angosta a un tamaño chico al dejar de ser franja completa", async () => {
  await render(<PantallaPanico />);
  const boton = await screen.findByTestId("boton-panico");
  expect(boton.props.style).not.toEqual(expect.objectContaining({ width: "100%" }));
});
