import { render, fireEvent, screen, waitFor } from "@testing-library/react-native";
import * as Linking from "expo-linking";
import NumerosEmergenciaScreen from "@/app/(vecino)/numeros-emergencia/index";
import * as numerosApi from "@/api/numerosEmergencia";

afterEach(() => jest.restoreAllMocks());

test("muestra la lista de números con su categoría", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([
    { id: 1, categoria: "bomberos", categoria_display: "Bomberos", nombre: "Bomberos", telefono: "132", es_nacional: true },
  ]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/bomberos/i);
  expect(screen.getByText(/132/)).toBeTruthy();
});

test("al tocar un número, llama con tel: limpiando los espacios del teléfono", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([
    { id: 2, categoria: "salud", categoria_display: "Salud/Ambulancia", nombre: "Salud Responde", telefono: "600 360 7777", es_nacional: true },
  ]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  const abrirSpy = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  await render(<NumerosEmergenciaScreen />);
  await fireEvent.press(await screen.findByText(/salud responde/i));
  expect(abrirSpy).toHaveBeenCalledWith("tel:6003607777");
});

test("muestra las propuestas propias con su estado", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([
    { id: 5, categoria: "electricidad", categoria_display: "Electricidad", nombre: "CGE", telefono: "800 800 767", nota: "", estado: "pendiente", estado_display: "Pendiente", fecha_creacion: "2026-10-01T00:00:00Z" },
  ]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/cge/i);
  expect(screen.getByText(/pendiente/i)).toBeTruthy();
});

test("al enviar el formulario de proponer, llama a proponerNumero y confirma", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  const proponerSpy = jest.spyOn(numerosApi, "proponerNumero").mockResolvedValue({
    id: 9, categoria: "otro", categoria_display: "Otro", nombre: "Conserjería", telefono: "123", nota: "", estado: "pendiente", estado_display: "Pendiente", fecha_creacion: "2026-10-01T00:00:00Z",
  });
  await render(<NumerosEmergenciaScreen />);
  await fireEvent.press(await screen.findByText(/proponer un número/i));
  fireEvent.changeText(screen.getByPlaceholderText(/nombre/i), "Conserjería");
  // Hallazgo: dos fireEvent.changeText seguidos sin esperar entre medio
  // dejaban una actualización de TextInput sin asentar del todo, lo que
  // contaminaba el test SIGUIENTE del archivo (su carga inicial nunca
  // avanzaba más allá de "cargando") -- este waitFor fuerza a asentar
  // cada cambio antes de seguir.
  await waitFor(() => expect(screen.getByPlaceholderText(/nombre/i).props.value).toBe("Conserjería"));
  fireEvent.changeText(screen.getByPlaceholderText(/teléfono/i), "123");
  await waitFor(() => expect(screen.getByPlaceholderText(/teléfono/i).props.value).toBe("123"));
  await fireEvent.press(screen.getByText(/^enviar$/i));
  expect(proponerSpy).toHaveBeenCalled();
  await screen.findByText(/gracias.*pendiente de revisión/i);
});

test("si falla la carga, muestra error y 'Reintentar'", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockRejectedValueOnce(new Error("sin red")).mockResolvedValueOnce([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/no se pudo cargar/i);
  await fireEvent.press(screen.getByText(/reintentar/i));
});
