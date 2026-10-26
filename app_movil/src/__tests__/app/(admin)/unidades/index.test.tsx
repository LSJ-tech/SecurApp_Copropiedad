import { render, fireEvent, screen } from "@testing-library/react-native";
import UnidadesScreen from "@/app/(admin)/unidades/index";
import * as unidadesApi from "@/api/unidades";
import * as torresApi from "@/api/torres";
import { ErrorDeServidor } from "@/api/client";

afterEach(() => jest.restoreAllMocks());

test("lista las unidades y permite crear una nueva sin torre", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest
    .spyOn(unidadesApi, "listarUnidades")
    .mockResolvedValue([{ id: 1, numero: "101", calle: "", torre: null, alicuota: null }]);
  const crearSpy = jest
    .spyOn(unidadesApi, "crearUnidad")
    .mockResolvedValue({ id: 2, numero: "102", calle: "", torre: null, alicuota: null });
  await render(<UnidadesScreen />);
  await screen.findByText("101");
  await fireEvent.changeText(screen.getByPlaceholderText(/número/i), "102");
  await fireEvent.press(screen.getByText(/agregar/i));
  expect(crearSpy).toHaveBeenCalledWith({ numero: "102" });
});

test("muestra la torre de cada unidad para distinguir numeros duplicados entre torres distintas (hallazgo Important: Empart real tiene numeros repetidos entre torres)", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([
    { id: 1, nombre: "Torre A" },
    { id: 2, nombre: "Torre B" },
  ]);
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([
    { id: 1, numero: "101", calle: "", torre: 1, alicuota: null },
    { id: 2, numero: "101", calle: "", torre: 2, alicuota: null },
  ]);
  await render(<UnidadesScreen />);
  await screen.findByText("101 · Torre A");
  await screen.findByText("101 · Torre B");
});

test("si falla cargar las unidades, muestra un error", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([]);
  jest.spyOn(unidadesApi, "listarUnidades").mockRejectedValue(new Error("sin red"));
  await render(<UnidadesScreen />);
  await screen.findByText(/no se pudieron cargar las unidades/i);
});

test("al elegir una torre del selector y agregar, crea la unidad con esa torre", async () => {
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([{ id: 5, nombre: "Torre C" }]);
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  const crearSpy = jest
    .spyOn(unidadesApi, "crearUnidad")
    .mockResolvedValue({ id: 3, numero: "303", calle: "", torre: 5, alicuota: null });
  await render(<UnidadesScreen />);
  await fireEvent.press(await screen.findByText(/sin torre/i));
  await fireEvent.press(await screen.findByText("Torre C"));
  await screen.findByText("Torre C");
  await fireEvent.changeText(screen.getByPlaceholderText(/número/i), "303");
  await fireEvent.press(screen.getByText(/agregar/i));
  expect(crearSpy).toHaveBeenCalledWith({ numero: "303", torre: 5 });
});

test("si la torre elegida no pertenece al condominio, muestra el mensaje real del backend", async () => {
  // Texto exacto confirmado contra el backend real (UnidadSerializer.validate,
  // core/serializers.py) -- no es un mensaje inventado para el test.
  jest.spyOn(torresApi, "listarTorres").mockResolvedValue([{ id: 9, nombre: "Z" }]);
  jest.spyOn(unidadesApi, "listarUnidades").mockResolvedValue([]);
  jest
    .spyOn(unidadesApi, "crearUnidad")
    .mockRejectedValue(new ErrorDeServidor(400, { torre: ["Esa torre pertenece a otro condominio."] }));
  await render(<UnidadesScreen />);
  await fireEvent.changeText(await screen.findByPlaceholderText(/número/i), "1");
  await fireEvent.press(screen.getByText(/agregar/i));
  await screen.findByText(/esa torre pertenece a otro condominio/i);
});
