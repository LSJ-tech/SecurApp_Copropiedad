import { render, fireEvent, screen } from "@testing-library/react-native";
import LoginScreen from "@/app/login";
import * as authContext from "@/auth/AuthContext";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("credenciales incorrectas muestran el mensaje de siempre", async () => {
  const iniciarSesionSpy = jest.fn().mockRejectedValue(new ErrorDeServidor(401));
  jest.spyOn(authContext, "useAuth").mockReturnValue({ iniciarSesion: iniciarSesionSpy } as any);
  await render(<LoginScreen />);
  await fireEvent.changeText(screen.getByPlaceholderText("Usuario"), "logan");
  await fireEvent.changeText(screen.getByPlaceholderText("Contraseña"), "mala");
  await fireEvent.press(screen.getByText("Ingresar"));
  await screen.findByText("Usuario o contraseña incorrectos.");
});

test("sin conexión, muestra un mensaje distinto -- no hace dudar de la contraseña", async () => {
  // Hallazgo real: un catch genérico mostraba "Usuario o contraseña
  // incorrectos." incluso sin red, haciendo dudar de la contraseña
  // cuando el problema era la conexión.
  const iniciarSesionSpy = jest.fn().mockRejectedValue(new ErrorDeRed("sin red"));
  jest.spyOn(authContext, "useAuth").mockReturnValue({ iniciarSesion: iniciarSesionSpy } as any);
  await render(<LoginScreen />);
  await fireEvent.changeText(screen.getByPlaceholderText("Usuario"), "logan");
  await fireEvent.changeText(screen.getByPlaceholderText("Contraseña"), "clave");
  await fireEvent.press(screen.getByText("Ingresar"));
  await screen.findByText(/no se pudo conectar/i);
  expect(screen.queryByText("Usuario o contraseña incorrectos.")).toBeNull();
});
