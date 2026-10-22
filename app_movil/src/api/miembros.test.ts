jest.mock("./client");

import { listarMiembros, crearMiembro } from "./miembros";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
  jest.clearAllMocks();
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

test("listarMiembros trae TODAS las páginas, no solo la primera (hallazgo Important: Empart real tiene 56+ membresías, 50/página)", async () => {
  (apiFetch as jest.Mock)
    .mockResolvedValueOnce({
      count: 2,
      next: "https://api.example.com/api/v1/miembros/?page=2",
      previous: null,
      results: [
        { id: 1, nombre: "Ana", rol: "residente", rol_display: "Residente", unidad_numero: "1", unidad_torre: null },
      ],
    })
    .mockResolvedValueOnce({
      count: 2,
      next: null,
      previous: "https://api.example.com/api/v1/miembros/",
      results: [
        { id: 2, nombre: "Beto", rol: "residente", rol_display: "Residente", unidad_numero: "2", unidad_torre: null },
      ],
    });
  const resultado = await listarMiembros();
  expect(resultado.map((m) => m.id)).toEqual([1, 2]);
  expect(apiFetch).toHaveBeenNthCalledWith(1, "/api/v1/miembros/");
  expect(apiFetch).toHaveBeenNthCalledWith(2, "/api/v1/miembros/?page=2");
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
