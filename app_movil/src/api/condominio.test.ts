jest.mock("./client");

import { obtenerMiCondominio, actualizarMiCondominio, regenerarCodigoInvitacion } from "./condominio";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("obtenerMiCondominio pide /api/v1/condominio/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({});
  await obtenerMiCondominio();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/condominio/");
});

test("actualizarMiCondominio hace PATCH", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({});
  await actualizarMiCondominio({ nombre: "Nuevo nombre" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/condominio/", {
    method: "PATCH",
    body: JSON.stringify({ nombre: "Nuevo nombre" }),
  });
});

test("regenerarCodigoInvitacion pega al endpoint correcto", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ token_registro_residentes: "abc" });
  await regenerarCodigoInvitacion();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/condominio/regenerar-token/", { method: "POST" });
});
