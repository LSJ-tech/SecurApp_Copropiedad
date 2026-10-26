import { render, fireEvent, screen } from "@testing-library/react-native";
import MiembrosScreen from "@/app/(admin)/miembros/index";
import * as miembrosApi from "@/api/miembros";
import * as unidadesApi from "@/api/unidades";
import * as torresApi from "@/api/torres";
import { ErrorDeServidor } from "@/api/client";

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

test("el campo de correo abre el teclado de email", async () => {
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  await render(<MiembrosScreen />);
  await screen.findByPlaceholderText("Correo");
  expect(screen.getByPlaceholderText("Correo").props.keyboardType).toBe("email-address");
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

test("al elegir una unidad del selector y crear, manda esa unidad", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([{ id: 1, nombre: "Torre A" }]);
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([
    { id: 7, numero: "101", calle: "", torre: 1, alicuota: null },
  ]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  const crearSpy = jest
    .spyOn(miembrosApi, "crearMiembro")
    .mockResolvedValue({ id: 1, username: "ana123", password_temporal: "xYz789" });
  await render(<MiembrosScreen />);
  await fireEvent.press(await screen.findByText(/sin unidad/i));
  await fireEvent.press(await screen.findByText("101 · Torre A"));
  await fireEvent.changeText(screen.getByPlaceholderText(/nombre/i), "Ana");
  await fireEvent.changeText(screen.getByPlaceholderText(/apellido/i), "Pérez");
  await fireEvent.changeText(screen.getByPlaceholderText(/correo/i), "a@test.cl");
  await fireEvent.press(screen.getByText(/crear miembro/i));
  expect(crearSpy).toHaveBeenCalledWith(
    expect.objectContaining({ unidad: 7 })
  );
});

test("se puede elegir el rol Delegado", async () => {
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  const crearSpy = jest
    .spyOn(miembrosApi, "crearMiembro")
    .mockResolvedValue({ id: 1, username: "ana123", password_temporal: "xYz789" });
  await render(<MiembrosScreen />);
  await fireEvent.press(await screen.findByText(/^delegado$/i));
  await fireEvent.changeText(screen.getByPlaceholderText(/nombre/i), "Ana");
  await fireEvent.changeText(screen.getByPlaceholderText(/apellido/i), "Pérez");
  await fireEvent.changeText(screen.getByPlaceholderText(/correo/i), "a@test.cl");
  await fireEvent.press(screen.getByText(/crear miembro/i));
  expect(crearSpy).toHaveBeenCalledWith(expect.objectContaining({ rol: "delegado" }));
});

test("si falla cargar los miembros, muestra un error", async () => {
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockRejectedValue(new Error("sin red"));
  await render(<MiembrosScreen />);
  await screen.findByText(/no se pudieron cargar los miembros/i);
});

test("si falla crear el miembro, muestra el mensaje real del backend", async () => {
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([]);
  jest
    .spyOn(miembrosApi, "crearMiembro")
    .mockRejectedValue(new ErrorDeServidor(400, { email: ["Ya existe una cuenta con ese correo."] }));
  await render(<MiembrosScreen />);
  await fireEvent.changeText(await screen.findByPlaceholderText(/nombre/i), "Ana");
  await fireEvent.changeText(screen.getByPlaceholderText(/apellido/i), "Pérez");
  await fireEvent.changeText(screen.getByPlaceholderText(/correo/i), "a@test.cl");
  await fireEvent.press(screen.getByText(/crear miembro/i));
  await screen.findByText(/ya existe una cuenta con ese correo/i);
});

test("muestra la lista de miembros ya cargados", async () => {
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(miembrosApi, "listarMiembros").mockResolvedValue([
    { id: 1, nombre: "Ana Pérez", rol_display: "Delegada" } as any,
  ]);
  await render(<MiembrosScreen />);
  await screen.findByText("Ana Pérez");
  await screen.findByText("Delegada");
});
