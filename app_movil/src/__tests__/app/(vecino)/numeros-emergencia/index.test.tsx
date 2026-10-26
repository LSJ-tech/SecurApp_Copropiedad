import { render, fireEvent, screen } from "@testing-library/react-native";
import * as Linking from "expo-linking";
import NumerosEmergenciaScreen from "@/app/(vecino)/numeros-emergencia/index";
import * as numerosApi from "@/api/numerosEmergencia";
import { ErrorDeServidor } from "@/api/client";
import { colores } from "@/theme/colores";

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

test("la lista es desplazable para que los nacionales no queden inalcanzables", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/números de emergencia/i);
  expect(screen.toJSON()?.type).toBe("RCTScrollView");
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

test("sin números cargados, muestra el estado vacío ilustrado en vez de quedar en blanco", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-sin-numeros");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })])
  );
  await screen.findByText(/todavía no hay números cargados/i);
});

test("sin números pero con una propuesta propia, se ven ambas cosas", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([
    { id: 1, categoria: "electricidad", categoria_display: "Electricidad", nombre: "Plomero", telefono: "900 000 000", nota: "", estado: "pendiente", estado_display: "Pendiente", fecha_creacion: "2026-10-01T00:00:00Z" },
  ]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByTestId("tarjeta-sin-numeros");
  await screen.findByText(/plomero/i);
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

test("al enviar el formulario de proponer, llama a proponerNumero con la categoría elegida y confirma", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  const proponerSpy = jest.spyOn(numerosApi, "proponerNumero").mockResolvedValue({
    id: 9, categoria: "electricidad", categoria_display: "Electricidad", nombre: "CGE", telefono: "800 800 767", nota: "", estado: "pendiente", estado_display: "Pendiente", fecha_creacion: "2026-10-01T00:00:00Z",
  });
  await render(<NumerosEmergenciaScreen />);
  await fireEvent.press(await screen.findByText(/proponer un número/i));
  // await en cada changeText (no fire-and-forget): este RTL (14.1.0)
  // trata fireEvent como async -- sin el await, el siguiente test del
  // archivo quedaba contaminado (su cargar() inicial nunca progresaba).
  await fireEvent.changeText(screen.getByPlaceholderText(/categoría/i), "electricidad");
  await fireEvent.changeText(screen.getByPlaceholderText(/^nombre$/i), "CGE");
  await fireEvent.changeText(screen.getByPlaceholderText(/teléfono/i), "800 800 767");
  await fireEvent.press(screen.getByText(/^enviar$/i));
  expect(proponerSpy).toHaveBeenCalledWith(
    expect.objectContaining({ categoria: "electricidad", nombre: "CGE", telefono: "800 800 767" })
  );
  await screen.findByText(/gracias.*pendiente de revisión/i);
});

test("si el backend rechaza un campo, muestra el mensaje real en vez del genérico", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  jest.spyOn(numerosApi, "proponerNumero").mockRejectedValue(
    new ErrorDeServidor(400, { nombre: ["Ese ya es un número nacional, no hace falta proponerlo."] })
  );
  await render(<NumerosEmergenciaScreen />);
  await fireEvent.press(await screen.findByText(/proponer un número/i));
  await fireEvent.changeText(screen.getByPlaceholderText(/^nombre$/i), "Carabineros");
  await fireEvent.changeText(screen.getByPlaceholderText(/teléfono/i), "133");
  await fireEvent.press(screen.getByText(/^enviar$/i));
  await screen.findByText(/ya es un número nacional/i);
});

test("si falla la carga, muestra error y 'Reintentar'", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockRejectedValueOnce(new Error("sin red")).mockResolvedValueOnce([]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  await screen.findByText(/no se pudo cargar/i);
  await fireEvent.press(screen.getByText(/reintentar/i));
});

test("cada número de la lista no lleva un color de fondo sólido", async () => {
  jest.spyOn(numerosApi, "listarNumerosEmergencia").mockResolvedValue([
    { id: 1, categoria: "bomberos", categoria_display: "Bomberos", nombre: "Bomberos", telefono: "132", es_nacional: true },
  ]);
  jest.spyOn(numerosApi, "listarMisPropuestas").mockResolvedValue([]);
  await render(<NumerosEmergenciaScreen />);
  const fila = await screen.findByTestId("fila-numero-0");
  const estilo = [fila.props.style].flat();
  expect(estilo).not.toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })]));
});
