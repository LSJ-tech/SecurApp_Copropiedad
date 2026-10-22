jest.mock("./client");

import { listarUnidades, crearUnidad } from "./unidades";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
  jest.clearAllMocks();
});

test("listarUnidades pide /api/v1/unidades/ y devuelve results", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [{ id: 1, numero: "101", calle: "", torre: null, alicuota: null }],
  });
  const resultado = await listarUnidades();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/unidades/");
  expect(resultado).toEqual([{ id: 1, numero: "101", calle: "", torre: null, alicuota: null }]);
});

test("listarUnidades trae TODAS las páginas, no solo la primera (hallazgo Important: Empart real tiene 352 unidades, 50/página)", async () => {
  (apiFetch as jest.Mock)
    .mockResolvedValueOnce({
      count: 3,
      next: "https://api.example.com/api/v1/unidades/?page=2",
      previous: null,
      results: [{ id: 1, numero: "1", calle: "", torre: null, alicuota: null }],
    })
    .mockResolvedValueOnce({
      count: 3,
      next: "https://api.example.com/api/v1/unidades/?page=3",
      previous: "https://api.example.com/api/v1/unidades/",
      results: [{ id: 2, numero: "2", calle: "", torre: null, alicuota: null }],
    })
    .mockResolvedValueOnce({
      count: 3,
      next: null,
      previous: "https://api.example.com/api/v1/unidades/?page=2",
      results: [{ id: 3, numero: "3", calle: "", torre: null, alicuota: null }],
    });
  const resultado = await listarUnidades();
  expect(resultado.map((u) => u.id)).toEqual([1, 2, 3]);
  expect(apiFetch).toHaveBeenNthCalledWith(1, "/api/v1/unidades/");
  expect(apiFetch).toHaveBeenNthCalledWith(2, "/api/v1/unidades/?page=2");
  expect(apiFetch).toHaveBeenNthCalledWith(3, "/api/v1/unidades/?page=3");
});

test("crearUnidad manda el payload dado", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 2, numero: "102", calle: "", torre: 1, alicuota: null });
  await crearUnidad({ numero: "102", torre: 1 });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/unidades/", {
    method: "POST",
    body: JSON.stringify({ numero: "102", torre: 1 }),
  });
});
