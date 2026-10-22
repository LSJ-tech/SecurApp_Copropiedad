import { render, fireEvent, screen } from "@testing-library/react-native";
import MiembrosScreen from "@/app/(admin)/miembros/index";
import * as miembrosApi from "@/api/miembros";
import * as unidadesApi from "@/api/unidades";
import * as torresApi from "@/api/torres";

afterEach(() => jest.restoreAllMocks());

test("al crear un miembro, muestra el usuario y la contraseña temporal generados", async () => {
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
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
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
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

test("el selector de unidad muestra la torre para distinguir numeros duplicados entre torres distintas (hallazgo Important)", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([
    { id: 1, nombre: "Torre A" },
    { id: 2, nombre: "Torre B" },
  ]);
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([
    { id: 1, numero: "101", calle: "", torre: 1, alicuota: null },
    { id: 2, numero: "101", calle: "", torre: 2, alicuota: null },
  ]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  await render(<MiembrosScreen />);
  await fireEvent.press(await screen.findByText(/sin unidad/i));
  await screen.findByText("101 · Torre A");
  await screen.findByText("101 · Torre B");
});
