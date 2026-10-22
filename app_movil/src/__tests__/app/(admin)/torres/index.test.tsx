import { render, fireEvent, screen } from "@testing-library/react-native";
import TorresScreen from "@/app/(admin)/torres/index";
import * as torresApi from "@/api/torres";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("lista las torres y permite crear una nueva", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([{ id: 1, nombre: "A" }]);
  const crearSpy = jest.spyOn(torresApi, "crearTorre").mockResolvedValue({ id: 2, nombre: "B" });
  await render(<TorresScreen />);
  await screen.findByText("A");
  await fireEvent.changeText(screen.getByPlaceholderText(/nombre/i), "B");
  await fireEvent.press(screen.getByText(/agregar/i));
  expect(crearSpy).toHaveBeenCalledWith("B");
  await screen.findByText("B");
});

test("si falla crear (ej. nombre vacío), muestra el mensaje real del backend", async () => {
  // Torre NO tiene restricción de nombre único (core/models.py) -- el único
  // error de validación real que TorreSerializer puede devolver es un
  // nombre vacío. Texto exacto confirmado contra el backend real.
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(torresApi, "crearTorre").mockRejectedValue(
    new ErrorDeServidor(400, { nombre: ["Este campo no puede estar en blanco."] })
  );
  await render(<TorresScreen />);
  await fireEvent.press(await screen.findByText(/agregar/i));
  await screen.findByText(/este campo no puede estar en blanco/i);
});

test("si falla listar, muestra un error", async () => {
  jest.spyOn(torresApi, "listarTorres").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<TorresScreen />);
  await screen.findByText(/no se pudieron cargar las torres/i);
});
