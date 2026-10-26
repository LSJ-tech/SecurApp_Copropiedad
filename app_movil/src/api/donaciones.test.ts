jest.mock("./client");

import { cancelarDonacion, crearDonacion, formatearMontoDonacion, obtenerMiDonacion } from "./donaciones";
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

describe("formatearMontoDonacion", () => {
  test("monto de un dígito, sin separador", () => {
    expect(formatearMontoDonacion("2000.00")).toBe("2.000");
  });

  test("menos de mil, sin separador", () => {
    expect(formatearMontoDonacion("500.00")).toBe("500");
  });

  test("millones, con dos separadores", () => {
    expect(formatearMontoDonacion("1234567.00")).toBe("1.234.567");
  });

  test("redondea los decimales", () => {
    expect(formatearMontoDonacion("1999.60")).toBe("2.000");
  });
});
