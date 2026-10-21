jest.mock("@/auth/AuthContext", () => ({ useAuth: () => ({ membresia: { rol: "delegado" } }) }));

import { render, fireEvent, screen } from "@testing-library/react-native";
import ListaAvisosScreen from "@/app/(vecino)/avisos/index";
import * as avisosApi from "@/api/avisos";

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
  const primeraPromesa = fireEvent.press(boton);
  const segundaPromesa = fireEvent.press(boton);
  resolverPrimera({ id: 9 });
  await Promise.all([primeraPromesa, segundaPromesa]);
  expect(crearSpy).toHaveBeenCalledTimes(1);
});
