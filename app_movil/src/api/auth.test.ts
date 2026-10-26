jest.mock("./client");

import { actualizarMiPerfil, login, logout, obtenerMiPerfil } from "./auth";
import { apiFetch } from "./client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("login hace POST a /auth/login/ con usuario y contraseña, sin reintentar sesión expirada", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ access: "a", refresh: "r", membresia: null });
  await login("logan", "clave");
  expect(apiFetch).toHaveBeenCalledWith(
    "/api/v1/auth/login/",
    { method: "POST", body: JSON.stringify({ username: "logan", password: "clave" }) },
    false
  );
});

test("obtenerMiPerfil pide /auth/me/", async () => {
  (apiFetch as jest.Mock).mockResolvedValue({ rol: "residente" });
  await obtenerMiPerfil();
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/auth/me/");
});

test("logout hace POST a /auth/logout/ con el refresh -- sin esto el token seguía válido hasta 30 días después", async () => {
  (apiFetch as jest.Mock).mockResolvedValue(undefined);
  await logout("mi-refresh");
  expect(apiFetch).toHaveBeenCalledWith("/api/v1/auth/logout/", {
    method: "POST",
    body: JSON.stringify({ refresh: "mi-refresh" }),
  });
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
