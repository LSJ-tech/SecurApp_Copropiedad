import { Alert } from "react-native";
import { render, fireEvent, screen } from "@testing-library/react-native";
import PantallaMiCondominio from "@/app/(admin)/condominio/index";
import * as condominioApi from "@/api/condominio";
import { ErrorDeRed, ErrorDeServidor } from "@/api/client";

const DATOS_BASE = {
  nombre: "Empart",
  etiqueta_organizacion: "condominio",
  direccion: "Calle 1",
  comuna: "Viña del Mar",
  region: "Valparaíso",
  datos_transferencia: "",
  etiqueta_torre: "Torre",
  etiqueta_unidad: "Departamento",
  genero_unidad: "m",
};

afterEach(() => jest.restoreAllMocks());

test("al montar, carga y pre-llena el formulario", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue({
    nombre: "Empart",
    etiqueta_organizacion: "condominio",
    direccion: "Calle 1",
    comuna: "Viña del Mar",
    region: "Valparaíso",
    datos_transferencia: "",
    etiqueta_torre: "Torre",
    etiqueta_unidad: "Departamento",
    genero_unidad: "m",
  });
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
});

test("si falla la carga, no muestra el formulario (mismo criterio que Mi perfil, Tanda 2 -- guardar sobre un formulario vacío borraría datos reales)", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<PantallaMiCondominio />);
  await screen.findByText(/no se pudo cargar/i);
  expect(screen.queryByText(/guardar/i)).toBeNull();
});

test("al tocar Regenerar código, pide confirmación antes de invalidar el link anterior", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue({
    nombre: "Empart",
    etiqueta_organizacion: "condominio",
    direccion: "",
    comuna: "",
    region: "",
    datos_transferencia: "",
    etiqueta_torre: "Torre",
    etiqueta_unidad: "Departamento",
    genero_unidad: "m",
  });
  const regenerarSpy = jest.spyOn(condominioApi, "regenerarCodigoInvitacion").mockResolvedValue({
    token_registro_residentes: "nuevo",
  });
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
  await fireEvent.press(screen.getByText(/regenerar código/i));
  expect(regenerarSpy).not.toHaveBeenCalled();
});

test("al editar un campo y guardar con éxito, confirma que se guardó", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue(DATOS_BASE);
  const actualizarSpy = jest.spyOn(condominioApi, "actualizarMiCondominio").mockResolvedValue(DATOS_BASE);
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
  await fireEvent.changeText(screen.getByPlaceholderText("Nombre"), "Empart 2");
  await fireEvent.press(screen.getByText(/^guardar$/i));
  expect(actualizarSpy).toHaveBeenCalledWith(expect.objectContaining({ nombre: "Empart 2" }));
  await screen.findByText(/tus datos quedaron actualizados/i);
});

test("si falla guardar, muestra el mensaje real del backend", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue(DATOS_BASE);
  jest.spyOn(condominioApi, "actualizarMiCondominio").mockRejectedValue(
    new ErrorDeServidor(400, { nombre: ["Este campo no puede estar vacío."] })
  );
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
  await fireEvent.press(screen.getByText(/^guardar$/i));
  await screen.findByText(/este campo no puede estar vacío/i);
});

test("al confirmar Regenerar en el diálogo, muestra el código nuevo", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue(DATOS_BASE);
  jest.spyOn(condominioApi, "regenerarCodigoInvitacion").mockResolvedValue({
    token_registro_residentes: "codigo-nuevo",
  });
  jest.spyOn(Alert, "alert").mockImplementation((_titulo, _mensaje, botones) => {
    botones?.[1]?.onPress?.();
  });
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
  await fireEvent.press(screen.getByText(/regenerar código/i));
  await screen.findByText(/codigo-nuevo/i);
});

test("si falla regenerar el código, muestra el error", async () => {
  jest.spyOn(condominioApi, "obtenerMiCondominio").mockResolvedValue(DATOS_BASE);
  jest.spyOn(condominioApi, "regenerarCodigoInvitacion").mockRejectedValue(new ErrorDeRed("sin red"));
  jest.spyOn(Alert, "alert").mockImplementation((_titulo, _mensaje, botones) => {
    botones?.[1]?.onPress?.();
  });
  await render(<PantallaMiCondominio />);
  await screen.findByDisplayValue("Empart");
  await fireEvent.press(screen.getByText(/regenerar código/i));
  await screen.findByText(/no se pudo guardar/i);
});
