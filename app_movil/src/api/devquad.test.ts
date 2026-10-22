jest.mock("./client");

import { listarCondominiosDevquad, entrarCondominio } from "./devquad";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("listarCondominiosDevquad pide /api/v1/devquad/condominios/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue([]);
  await listarCondominiosDevquad();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/devquad/condominios/");
});

test("entrarCondominio manda el refresh actual al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({
    access: "a",
    refresh: "r",
    condominio: { id: 1, nombre: "X", plan: "premium", puede_operar: true },
  });
  await entrarCondominio(1, "refresh-actual");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/devquad/condominios/1/entrar/", {
    method: "POST",
    body: JSON.stringify({ refresh: "refresh-actual" }),
  });
});
