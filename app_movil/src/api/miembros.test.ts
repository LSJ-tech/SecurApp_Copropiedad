jest.mock("./client");

import { listarMiembros, crearMiembro } from "./miembros";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("listarMiembros pide /api/v1/miembros/ y devuelve results", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [
      { id: 1, nombre: "Ana", rol: "residente", rol_display: "Residente", unidad_numero: null, unidad_torre: null },
    ],
  });
  const resultado = await listarMiembros();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/miembros/");
  expect(resultado).toEqual([
    { id: 1, nombre: "Ana", rol: "residente", rol_display: "Residente", unidad_numero: null, unidad_torre: null },
  ]);
});

test("crearMiembro manda el payload dado", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 2, username: "ana123", password_temporal: "xYz789" });
  const resultado = await crearMiembro({
    nombre: "Ana",
    apellido: "Pérez",
    email: "a@test.cl",
    rol: "residente",
    unidad: 1,
  });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/miembros/", {
    method: "POST",
    body: JSON.stringify({ nombre: "Ana", apellido: "Pérez", email: "a@test.cl", rol: "residente", unidad: 1 }),
  });
  expect(resultado.password_temporal).toBe("xYz789");
});
