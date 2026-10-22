jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
  setNotificationHandler: jest.fn(),
  getLastNotificationResponseAsync: jest.fn(),
}));

import { render, fireEvent, screen } from "@testing-library/react-native";
import ElegirCondominioScreen from "@/app/elegir-condominio";
import * as devquadApi from "@/api/devquad";
import * as authContext from "@/auth/AuthContext";
import { ErrorDeRed } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("lista los condominios y al tocar uno llama a elegirCondominio", async () => {
  jest.spyOn(devquadApi, "listarCondominiosDevquad").mockResolvedValue([
    { id: 5, nombre: "Empart", plan: "premium", puede_operar: true },
  ]);
  const elegirSpy = jest.fn().mockResolvedValue(undefined);
  jest.spyOn(authContext, "useAuth").mockReturnValue({ elegirCondominio: elegirSpy } as any);
  await render(<ElegirCondominioScreen />);
  await fireEvent.press(await screen.findByText("Empart"));
  expect(elegirSpy).toHaveBeenCalledWith(5);
});

test("si falla listar los condominios, muestra un error", async () => {
  jest.spyOn(devquadApi, "listarCondominiosDevquad").mockRejectedValue(new ErrorDeRed("sin red"));
  jest.spyOn(authContext, "useAuth").mockReturnValue({ elegirCondominio: jest.fn() } as any);
  await render(<ElegirCondominioScreen />);
  await screen.findByText(/no se pudieron cargar los condominios/i);
});

test("si elegirCondominio falla, muestra un error y deja reintentar (no queda en un estado intermedio raro)", async () => {
  jest.spyOn(devquadApi, "listarCondominiosDevquad").mockResolvedValue([
    { id: 5, nombre: "Empart", plan: "premium", puede_operar: true },
  ]);
  const elegirSpy = jest.fn().mockRejectedValue(new ErrorDeRed("sin red"));
  jest.spyOn(authContext, "useAuth").mockReturnValue({ elegirCondominio: elegirSpy } as any);
  await render(<ElegirCondominioScreen />);
  await fireEvent.press(await screen.findByText("Empart"));
  await screen.findByText(/no se pudo entrar a ese condominio/i);
  await fireEvent.press(screen.getByText("Empart"));
  expect(elegirSpy).toHaveBeenCalledTimes(2);
});
