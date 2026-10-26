jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ membresia: { rol: "delegado" } }) }));

import { render, screen } from "@testing-library/react-native";
import DirectorioScreen from "@/app/(vecino)/directorio/index";
import * as directorioApi from "@/api/directorio";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";
import { colores } from "@/theme/colores";

afterEach(() => jest.restoreAllMocks());

test("lista nombre y unidad de cada miembro", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockResolvedValue([{ nombre: "Ana Pérez", torre: "A", unidad: "101" }]);
  await render(<DirectorioScreen />);
  await screen.findByText("Ana Pérez");
});

test("si el backend rechaza con 403 (residente, por deep link), muestra un mensaje en vez de romper", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockRejectedValue(new ErrorDeServidor(403));
  await render(<DirectorioScreen />);
  await screen.findByText(/no tienes acceso al directorio/i);
});

test("si falla por red, muestra un error en vez de un rechazo sin manejar", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<DirectorioScreen />);
  await screen.findByText(/no se pudo cargar el directorio/i);
});

test("cada fila no lleva un color de fondo sólido (D-03: solo acento, nunca relleno completo)", async () => {
  jest.spyOn(directorioApi, "listarDirectorio").mockResolvedValue([{ nombre: "Ana Pérez", torre: "A", unidad: "101" }]);
  await render(<DirectorioScreen />);
  const fila = await screen.findByTestId("fila-directorio-0");
  const estilo = [fila.props.style].flat();
  expect(estilo).not.toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })]));
});
