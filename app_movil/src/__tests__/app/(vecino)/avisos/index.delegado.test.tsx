jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ membresia: { rol: "delegado" } }) }));

import { act, render, fireEvent, screen } from "@testing-library/react-native";
import ListaAvisosScreen from "@/app/(vecino)/avisos/index";
import * as avisosApi from "@/api/avisos";
import { colores } from "@/theme/colores";

afterEach(() => jest.restoreAllMocks());

test("un delegado ve el formulario y puede publicar un aviso", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  const crearSpy = jest.spyOn(avisosApi, "crearAviso").mockResolvedValue({ id: 9 } as any);
  await render(<ListaAvisosScreen />);
  await screen.findByText(/publicar aviso/i);
  await fireEvent.changeText(screen.getByPlaceholderText(/título/i), "Corte de agua");
  await fireEvent.changeText(screen.getByPlaceholderText(/mensaje/i), "Mañana 9-12h");
  await fireEvent.press(screen.getByText(/publicar aviso/i));
  expect(crearSpy).toHaveBeenCalledWith({ titulo: "Corte de agua", cuerpo: "Mañana 9-12h" });
});

test("dos toques seguidos en Publicar aviso no mandan el aviso dos veces (hallazgo Important: push duplicado a todo el condominio)", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  let resolverPrimera: (valor: any) => void = () => {};
  const esperaPrimera = new Promise((resolve) => {
    resolverPrimera = resolve;
  });
  const crearSpy = jest.spyOn(avisosApi, "crearAviso").mockReturnValue(esperaPrimera as any);
  await render(<ListaAvisosScreen />);
  await screen.findByText(/publicar aviso/i);
  await fireEvent.changeText(screen.getByPlaceholderText(/título/i), "Corte de agua");
  await fireEvent.changeText(screen.getByPlaceholderText(/mensaje/i), "Mañana 9-12h");
  const boton = screen.getByText(/publicar aviso/i);
  // fireEvent.press no espera a que termine el handler async completo --
  // dos llamadas sueltas (sin envolver) dejaban la continuación de
  // manejarPublicar (el finally que libera publicandoRef) pendiente al
  // terminar este test, y disparaba durante el siguiente (mismo tipo de
  // hallazgo ya visto con fireEvent.changeText sin await en
  // numeros-emergencia) -- un solo act() alrededor de las dos pulsaciones
  // fuerza a asentar todo antes de seguir.
  await act(async () => {
    fireEvent.press(boton);
    fireEvent.press(boton);
    resolverPrimera({ id: 9 });
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(crearSpy).toHaveBeenCalledTimes(1);
});

test("el formulario de publicar usa el color de fondo informativo", async () => {
  jest.spyOn(avisosApi, "listarAvisos").mockResolvedValue([]);
  await render(<ListaAvisosScreen />);
  await screen.findByText(/publicar aviso/i);
  const tarjeta = screen.getByTestId("tarjeta-formulario-aviso");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })])
  );
});
