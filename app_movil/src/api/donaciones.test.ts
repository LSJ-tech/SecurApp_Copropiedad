jest.mock("./client");

import { cancelarDonacion, crearDonacion, obtenerMiDonacion } from "./donaciones";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("obtenerMiDonacion pide /api/v1/pagos/mi-donacion/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({
    donacion_actual: null, pagos: [], total_donado: "0.00", cantidad_aportes: 0,
  });
  await obtenerMiDonacion();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/pagos/mi-donacion/");
});

test("crearDonacion pide POST /api/v1/pagos/donar/ sin body", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ url_autorizacion: "https://mercadopago.cl/autorizar/1" });
  const resultado = await crearDonacion();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/pagos/donar/", { method: "POST" });
  expect(resultado.url_autorizacion).toBe("https://mercadopago.cl/autorizar/1");
});

test("cancelarDonacion pide POST /api/v1/pagos/donar/cancelar/ sin body", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ detail: "Listo." });
  await cancelarDonacion();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/pagos/donar/cancelar/", { method: "POST" });
});
