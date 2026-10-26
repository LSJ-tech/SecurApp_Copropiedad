jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: "7" }),
}));

import { render, screen } from "@testing-library/react-native";
import DetalleAlertaScreen from "@/app/(vecino)/alertas/[id]";
import * as alertasApi from "@/api/alertas";
import { ErrorDeRed } from "@/api/client";
import { colores } from "@/theme/colores";

afterEach(() => {
  jest.restoreAllMocks();
});

test("si obtenerAlerta falla, muestra un error en vez de quedar en blanco para siempre", async () => {
  // Hallazgo I8 de la revisión final: .then(setAlerta) sin .catch
  // dejaba la pantalla en blanco (return null) para siempre ante
  // cualquier error -- 404, sin red, sesión expirada.
  jest.spyOn(alertasApi, "obtenerAlerta").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<DetalleAlertaScreen />);
  await screen.findByText(/no se pudo cargar la alerta/i);
});

test("el bloque de datos de la alerta usa el color de fondo informativo", async () => {
  jest.spyOn(alertasApi, "obtenerAlerta").mockResolvedValue({
    id: 7, tipo_display: "Robo", estado: "activa", estado_display: "Activa", mensaje: "", autor_nombre: "Ana", visto_por_count: null,
  } as any);
  await render(<DetalleAlertaScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-detalle-alerta");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })])
  );
});
