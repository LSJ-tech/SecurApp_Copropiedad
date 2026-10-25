import { act, render, fireEvent, screen, waitFor } from "@testing-library/react-native";
import { AppState } from "react-native";
import * as Linking from "expo-linking";
import DonarScreen from "@/app/(vecino)/donar/index";
import * as donacionesApi from "@/api/donaciones";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

afterEach(() => {
  jest.restoreAllMocks();
  // AppState.addEventListener ya viene pre-mockeado por el preset
  // jest-expo (un jest.fn() persistente, no un spy sobre una
  // implementación real) -- restoreAllMocks() no tiene nada que
  // restaurar ahí, así que su historial de llamadas se arrastraba de
  // un test al otro sin este clearAllMocks (mismo patrón ya visto en
  // unidades.test.ts).
  jest.clearAllMocks();
});

test("sin donación activa, muestra el monto fijo y un botón Donar", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/\$2\.000/);
  expect(screen.getByText(/^donar$/i)).toBeTruthy();
});

test("al tocar Donar, abre la URL de autorización en el navegador", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  jest.spyOn(donacionesApi, "crearDonacion").mockResolvedValue({ url_autorizacion: "https://mercadopago.cl/autorizar/123" });
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<DonarScreen />);
  await fireEvent.press(await screen.findByText(/^donar$/i));
  await waitFor(() => expect(abrirSpy).toHaveBeenCalledWith("https://mercadopago.cl/autorizar/123"));
});

test("con una donación autorizada, muestra el estado y un botón Cancelar en vez de Donar", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
    pagos: [], total_donado: "6000.00", cantidad_aportes: 3,
  });
  await render(<DonarScreen />);
  await screen.findByText(/autorizada/i);
  expect(screen.getByText(/cancelar/i)).toBeTruthy();
  expect(screen.queryByText(/^donar$/i)).toBeNull();
});

test("con una donación pendiente, también muestra Cancelar (el backend la acepta en pendiente o autorizada)", async () => {
  // Hallazgo Critical de la revisión final: donar/cancelar() del backend
  // acepta estado__in=["pendiente","autorizada"] -- la pantalla tiene que
  // decidir por el MISMO criterio, o muestra un botón que el backend va
  // a rechazar.
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: { estado: "pendiente", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
    pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/pendiente/i);
  expect(screen.getByText(/cancelar/i)).toBeTruthy();
});

test.each(["cancelada", "pausada"])(
  "con una donación %s, muestra Donar de nuevo, no Cancelar (hallazgo Critical: quedaba trabado para siempre)",
  async (estado) => {
    jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
      donacion_actual: { estado, monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
      pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
    });
    await render(<DonarScreen />);
    await screen.findByText(/^donar$/i);
    expect(screen.queryByText(/cancelar/i)).toBeNull();
  }
);

test("si falla crear la donación, muestra el mensaje real del backend en vez de romper", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  jest.spyOn(donacionesApi, "crearDonacion").mockRejectedValue(
    new ErrorDeServidor(400, { detail: "Agrega tu email en «Mi perfil» antes de activar una donación automática." })
  );
  await render(<DonarScreen />);
  await fireEvent.press(await screen.findByText(/^donar$/i));
  await screen.findByText(/agrega tu email/i);
});

test("al cancelar con éxito, vuelve a mostrar el botón Donar", async () => {
  // El backend real deja la SuscripcionRecurrente en estado "cancelada"
  // (nunca la borra ni la pone en null) -- no "donacion_actual: null".
  jest
    .spyOn(donacionesApi, "obtenerMiDonacion")
    .mockResolvedValueOnce({
      donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
      pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
    })
    .mockResolvedValueOnce({
      donacion_actual: { estado: "cancelada", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
      pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
    });
  jest.spyOn(donacionesApi, "cancelarDonacion").mockResolvedValue(undefined);
  await render(<DonarScreen />);
  await fireEvent.press(await screen.findByText(/cancelar/i));
  await screen.findByText(/^donar$/i);
});

test("si falla la carga inicial, muestra un error y 'Reintentar' en vez de quedar en blanco (hallazgo Important)", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockRejectedValueOnce(new ErrorDeRed("sin red")).mockResolvedValueOnce({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/no se pudo cargar tu donación/i);
  await fireEvent.press(screen.getByText(/reintentar/i));
  await screen.findByText(/^donar$/i);
});

test("al volver del navegador externo (app vuelve a 'active'), recarga la donación (hallazgo Important)", async () => {
  // Hallazgo de la revisión final: sin esto, volver de autorizar el pago
  // en Mercado Pago dejaba la pantalla con los datos de ANTES de donar
  // hasta reiniciar la app entera.
  const addEventListenerSpy = jest.spyOn(AppState, "addEventListener");
  jest
    .spyOn(donacionesApi, "obtenerMiDonacion")
    .mockResolvedValueOnce({ donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0 })
    .mockResolvedValueOnce({
      donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
      pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
    });
  await render(<DonarScreen />);
  await screen.findByText(/^donar$/i);

  const listener = addEventListenerSpy.mock.calls.find((c) => c[0] === "change")?.[1];
  await act(async () => {
    await listener?.("active");
  });

  await screen.findByText(/autorizada/i);
});

test("muestra el total donado y la cantidad de aportes cuando hay historial", async () => {
  // Monto del pago distinto del total para que ningún texto sea ambiguo
  // entre el resumen ("Has aportado...") y la fila del historial -- con
  // un solo aporte de igual monto que el total, ambos textos contienen
  // "$2.000" y la consulta por texto se vuelve ambigua.
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null,
    pagos: [
      { estado: "aprobado", monto: "2000.00", fecha_creacion: "2026-09-01T00:00:00Z" },
      { estado: "aprobado", monto: "2000.00", fecha_creacion: "2026-08-01T00:00:00Z" },
    ],
    total_donado: "4000.00",
    cantidad_aportes: 2,
  });
  await render(<DonarScreen />);
  await screen.findByText(/has aportado \$4\.000 en 2 aportes/i);
});

test("sin historial, muestra un mensaje en vez de una lista vacía", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/todavía no tienes donaciones/i);
});

test("la pantalla es desplazable para que el historial no quede inalcanzable", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/^donar$/i);
  expect(screen.toJSON()?.type).toBe("RCTScrollView");
});

test("con pagos pero ninguno aprobado, no muestra el resumen de $0 en 0 aportes", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: null,
    pagos: [{ estado: "pendiente", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" }],
    total_donado: "0.00",
    cantidad_aportes: 0,
  });
  await render(<DonarScreen />);
  await screen.findByText(/pendiente/i);
  expect(screen.queryByText(/0 aportes/i)).toBeNull();
});
