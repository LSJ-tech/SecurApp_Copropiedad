jest.mock("./client");

import { listarUnidades, crearUnidad } from "./unidades";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
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

test("crearUnidad manda el payload dado", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ id: 2, numero: "102", calle: "", torre: 1, alicuota: null });
  await crearUnidad({ numero: "102", torre: 1 });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/unidades/", {
    method: "POST",
    body: JSON.stringify({ numero: "102", torre: 1 }),
  });
});
