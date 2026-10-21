jest.mock("expo-router", () => ({
  useLocalSearchParams: () => ({ id: "7" }),
}));

import { render, screen } from "@testing-library/react-native";
import DetalleAlertaScreen from "@/app/(vecino)/alertas/[id]";
import * as alertasApi from "@/api/alertas";
import { ErrorDeRed } from "@/api/client";

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
