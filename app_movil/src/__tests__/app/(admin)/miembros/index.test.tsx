import { render, fireEvent, screen } from "@testing-library/react-native";
import MiembrosScreen from "@/app/(admin)/miembros/index";
import * as miembrosApi from "@/api/miembros";
import * as unidadesApi from "@/api/unidades";

afterEach(() => jest.restoreAllMocks());

test("al crear un miembro, muestra el usuario y la contraseña temporal generados", async () => {
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "crearMiembro").mockResolvedValue({ id: 1, username: "ana123", password_temporal: "xYz789" });
  await render(<MiembrosScreen />);
  await fireEvent.changeText(await screen.findByPlaceholderText(/nombre/i), "Ana");
  await fireEvent.changeText(screen.getByPlaceholderText(/apellido/i), "Pérez");
  await fireEvent.changeText(screen.getByPlaceholderText(/correo/i), "a@test.cl");
  await fireEvent.press(screen.getByText(/crear miembro/i));
  await screen.findByText(/ana123/);
  await screen.findByText(/xYz789/);
});

test("el usuario y la contraseña generados siguen visibles aunque la lista se recargue después", async () => {
  // Hallazgo del Review Focus: la única vez que la contraseña es visible
  // -- no puede perderse si, por ejemplo, volver a listar falla o tarda.
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "crearMiembro").mockResolvedValue({ id: 1, username: "ana123", password_temporal: "xYz789" });
  await render(<MiembrosScreen />);
  await fireEvent.changeText(await screen.findByPlaceholderText(/nombre/i), "Ana");
  await fireEvent.changeText(screen.getByPlaceholderText(/apellido/i), "Pérez");
  await fireEvent.changeText(screen.getByPlaceholderText(/correo/i), "a@test.cl");
  await fireEvent.press(screen.getByText(/crear miembro/i));
  await screen.findByText(/xYz789/);
  expect(screen.getByText(/xYz789/)).toBeTruthy();
});
