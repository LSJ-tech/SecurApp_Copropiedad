jest.mock("./client");

import { listarNumerosEmergencia, listarMisPropuestas, proponerNumero } from "./numerosEmergencia";
import { apiFetch } from "./client";

afterEach(() => jest.restoreAllMocks());

test("listarNumerosEmergencia pide GET /api/v1/numeros-emergencia/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarNumerosEmergencia();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/numeros-emergencia/");
});

test("listarMisPropuestas pide GET /api/v1/propuestas-numero-emergencia/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarMisPropuestas();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/propuestas-numero-emergencia/");
});

test("proponerNumero pide POST /api/v1/propuestas-numero-emergencia/ con el payload", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 1 });
  await proponerNumero({ categoria: "electricidad", nombre: "CGE", telefono: "800 800 767" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/propuestas-numero-emergencia/", {
    method: "POST",
    body: JSON.stringify({ categoria: "electricidad", nombre: "CGE", telefono: "800 800 767" }),
  });
});
