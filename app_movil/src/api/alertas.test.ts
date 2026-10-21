jest.mock("./client");

import { listarAlertas, marcarVisto, obtenerAlerta } from "./alertas";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("listarAlertas sin estado pide /api/v1/alertas/ sin query", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarAlertas();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/");
});

test("listarAlertas con estado arma el query param", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarAlertas("activa");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/?estado=activa");
});

test("marcarVisto pega al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 3 });
  await marcarVisto(3);
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/3/marcar_visto/", { method: "POST" });
});

test("obtenerAlerta pide el detalle de una alerta por id", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 7 });
  await obtenerAlerta(7);
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/7/");
});
