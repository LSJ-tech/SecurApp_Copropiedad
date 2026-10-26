jest.mock("./client");

import { crearAlerta, listarAlertas, marcarVisto, obtenerAlerta, resolverAlerta } from "./alertas";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("crearAlerta hace POST a /api/v1/alertas/ con el payload exacto -- el llamado más crítico de toda la app", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 9 });
  await crearAlerta({ tipo: "incendio", latitud: -33.45, longitud: -70.65 });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/", {
    method: "POST",
    body: JSON.stringify({ tipo: "incendio", latitud: -33.45, longitud: -70.65 }),
  });
});

test("resolverAlerta hace PATCH a /resolver/ con el estado dado", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 9, estado: "falsa_alarma" });
  await resolverAlerta(9, "falsa_alarma");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/alertas/9/resolver/", {
    method: "PATCH",
    body: JSON.stringify({ estado: "falsa_alarma" }),
  });
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
