jest.mock("./client");

import { actualizarMiPerfil } from "./auth";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("actualizarMiPerfil hace PATCH a /auth/me/ con los campos dados", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({
    first_name: "Ana",
    last_name: "P",
    email: "a@test.cl",
    telefono: "123",
  });
  const resultado = await actualizarMiPerfil({ first_name: "Ana", telefono: "123" });
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/auth/me/", {
    method: "PATCH",
    body: JSON.stringify({ first_name: "Ana", telefono: "123" }),
  });
  expect(resultado.first_name).toBe("Ana");
});
