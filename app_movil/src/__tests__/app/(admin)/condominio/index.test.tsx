import { render, fireEvent, screen } from "@testing-library/react-native";
import PantallaMiCondominio from "@/app/(admin)/condominio/index";
import * as condominioApi from "@/api/condominio";
import { ErrorDeRed } from "@/api/client";

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
