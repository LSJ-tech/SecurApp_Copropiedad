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
