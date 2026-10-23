import { render, fireEvent, screen, waitFor } from "@testing-library/react-native";
import * as Linking from "expo-linking";
import DonarScreen from "@/app/(vecino)/donar/index";
import * as donacionesApi from "@/api/donaciones";
import { ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

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

test("con una donación activa, muestra el estado y un botón Cancelar en vez de Donar", async () => {
  jest.spyOn(donacionesApi, "obtenerMiDonacion").mockResolvedValue({
    donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
    pagos: [], total_donado: "6000.00", cantidad_aportes: 3,
  });
  await render(<DonarScreen />);
  await screen.findByText(/autorizada/i);
  expect(screen.getByText(/cancelar/i)).toBeTruthy();
  expect(screen.queryByText(/^donar$/i)).toBeNull();
});

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
  jest
    .spyOn(donacionesApi, "obtenerMiDonacion")
    .mockResolvedValueOnce({
      donacion_actual: { estado: "autorizada", monto: "2000.00", fecha_creacion: "2026-10-01T00:00:00Z" },
      pagos: [], total_donado: "2000.00", cantidad_aportes: 1,
    })
    .mockResolvedValueOnce({ donacion_actual: null, pagos: [], total_donado: "2000.00", cantidad_aportes: 1 });
  jest.spyOn(donacionesApi, "cancelarDonacion").mockResolvedValue(undefined);
  await render(<DonarScreen />);
  await fireEvent.press(await screen.findByText(/cancelar/i));
  await screen.findByText(/^donar$/i);
});
