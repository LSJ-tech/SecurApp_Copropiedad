jest.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({ membresia: { rol: "residente" } }),
}));

import { act, render, fireEvent, screen } from "@testing-library/react-native";
import * as Linking from "expo-linking";
import PantallaPerfil from "@/app/(vecino)/perfil/index";
import * as authApi from "@/api/auth";
import { ErrorDeRed, ErrorDeServidor, API_BASE_URL } from "@/api/client";
import { colores } from "@/theme/colores";

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

test("el botón Cambiar contraseña abre la página web en el navegador externo", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<PantallaPerfil />);
  await fireEvent.press(await screen.findByText(/cambiar contraseña/i));
  expect(abrirSpy).toHaveBeenCalledWith(`${API_BASE_URL}/mi-perfil/cambiar-contrasena/`);
});

test("el botón Solicitar eliminación de cuenta abre la página web en el navegador externo", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<PantallaPerfil />);
  await fireEvent.press(await screen.findByText(/solicitar eliminación de cuenta/i));
  expect(abrirSpy).toHaveBeenCalledWith(`${API_BASE_URL}/mi-perfil/eliminar-cuenta/`);
});

test("dos toques seguidos en Guardar no mandan dos PATCH (hallazgo: era la única pantalla sin esta guarda)", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  let resolverPrimera: (valor: any) => void = () => {};
  const esperaPrimera = new Promise((resolve) => {
    resolverPrimera = resolve;
  });
  const actualizarSpy = jest.spyOn(authApi, "actualizarMiPerfil").mockReturnValue(esperaPrimera as any);
  await render(<PantallaPerfil />);
  await screen.findByDisplayValue("Ana");
  const boton = screen.getByText(/guardar/i);
  await act(async () => {
    fireEvent.press(boton);
    fireEvent.press(boton);
    resolverPrimera({ first_name: "Ana", last_name: "Pérez", email: "ana@test.cl", telefono: "" });
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(actualizarSpy).toHaveBeenCalledTimes(1);
});

test("el correo y el teléfono abren el teclado correspondiente", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  await render(<PantallaPerfil />);
  await screen.findByDisplayValue("Ana");
  expect(screen.getByPlaceholderText("Correo").props.keyboardType).toBe("email-address");
  expect(screen.getByPlaceholderText("Teléfono").props.keyboardType).toBe("phone-pad");
});

test("el formulario principal usa el color de fondo informativo", async () => {
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    rol: "residente", condominio: { id: 1, nombre: "X" }, unidad: null,
    nombre: "Ana Pérez", telefono: "", first_name: "Ana", last_name: "Pérez", email: "ana@test.cl",
  });
  await render(<PantallaPerfil />);
  const tarjeta = await screen.findByTestId("tarjeta-perfil");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })])
  );
});
