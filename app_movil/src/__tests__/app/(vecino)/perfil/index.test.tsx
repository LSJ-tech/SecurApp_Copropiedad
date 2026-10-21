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

test("si falla la carga del perfil, muestra un error en vez de quedar en blanco", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<PantallaPerfil />);
  await screen.findByText(/no se pudo cargar tu perfil/i);
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
