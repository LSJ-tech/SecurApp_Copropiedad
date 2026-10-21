jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({ membresia: { rol: "residente" } }),
}));

import { render, fireEvent, screen } from "@testing-library/react-native";
import PantallaPerfil from "@/app/(vecino)/perfil/index";
import * as authApi from "@/api/auth";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("al montar, carga el perfil y pre-llena el formulario", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente",
    condominio: { id: 1, nombre: "X" },
    unidad: null,
    nombre: "Ana Pérez",
    telefono: "123",
    first_name: "Ana",
    last_name: "Pérez",
    email: "ana@test.cl",
  });
  await render(<PantallaPerfil />);
  await screen.findByDisplayValue("Ana");
  expect(screen.getByDisplayValue("ana@test.cl")).toBeTruthy();
});

test("si falla la carga del perfil, muestra un error Y NO el formulario (hallazgo Critical: guardar con el formulario vacío borraba los datos reales)", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockRejectedValue(new ErrorDeRed("sin red"));
  const actualizarSpy = jest.spyOn(authApi, "actualizarMiPerfil");
  await render(<PantallaPerfil />);
  await screen.findByText(/no se pudo cargar tu perfil/i);
  expect(screen.queryByText(/guardar/i)).toBeNull();
  expect(actualizarSpy).not.toHaveBeenCalled();
});

test("si falla la carga, 'Reintentar' vuelve a pedir el perfil", async () => {
  jest
    .spyOn(authApi, "obtenerMiPerfil")
    .mockRejectedValueOnce(new ErrorDeRed("sin red"))
    .mockResolvedValueOnce({
      rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
      nombre: "Ana Pérez", telefono: "123", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
    });
  await render(<PantallaPerfil />);
  await fireEvent.press(await screen.findByText(/reintentar/i));
  await screen.findByDisplayValue("Ana");
});

test("si el email ya está en uso, muestra el mensaje real del backend", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente",
    condominio: { id: 1, nombre: "X" },
    unidad: null,
    nombre: "Ana Pérez",
    telefono: "",
    first_name: "Ana",
    last_name: "Pérez",
    email: "ana@test.cl",
  });
  jest
    .spyOn(authApi, "actualizarMiPerfil")
    .mockRejectedValue(new ErrorDeServidor(400, { email: ["Ya existe otra cuenta con ese correo."] }));
  await render(<PantallaPerfil />);
  await screen.findByDisplayValue("Ana");
  await fireEvent.press(screen.getByText(/guardar/i));
  await screen.findByText(/ya existe otra cuenta con ese correo/i);
});

test("al guardar con éxito, confirma que se guardó (hallazgo Important: antes no pasaba nada visible)", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  jest.spyOn(authApi, "actualizarMiPerfil").mockResolvedValue({
    first_name: "Ana", last_name: "Pérez", email: "ana@test.cl", telefono: "",
  });
  await render(<PantallaPerfil />);
  await screen.findByDisplayValue("Ana");
  await fireEvent.press(screen.getByText(/guardar/i));
  await screen.findByText(/tus datos quedaron actualizados/i);
});
