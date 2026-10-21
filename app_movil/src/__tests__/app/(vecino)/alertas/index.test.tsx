import { render, screen } from "@testing-library/react-native";
import ListaAlertasScreen from "@/app/(vecino)/alertas/index";
import * as alertasApi from "@/api/alertas";
import { ErrorDeRed } from "@/api/client";

afterEach(() => {
  jest.restoreAllMocks();
});

test("si listar las alertas falla, muestra un error en vez de un rechazo sin manejar", async () => {
  // Hallazgo I8 de la revisión final: .then(setActivas) sin .catch
  // dejaba un unhandled rejection si no había red.
  jest.spyOn(alertasApi, "listarAlertas").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<ListaAlertasScreen />);
  await screen.findByText(/no se pudieron cargar las alertas/i);
});
