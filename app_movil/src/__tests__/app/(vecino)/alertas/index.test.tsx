import { render, screen } from "@testing-library/react-native";
import ListaAlertasScreen from "@/app/(vecino)/alertas/index";
import * as alertasApi from "@/api/alertas";
import { ErrorDeRed } from "@/api/client";
import { colores } from "@/theme/colores";

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

test("una fila de Activas lleva el color de fondo de peligro (excepción a la regla general)", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockImplementation((estado?: string) =>
    Promise.resolve(estado === "activa" ? [{ id: 1, tipo_display: "Robo", estado: "activa", estado_display: "Activa" } as any] : [])
  );
  await render(<ListaAlertasScreen />);
  const fila = await screen.findByTestId("fila-activa-0");
  const estilo = [fila.props.style].flat();
  expect(estilo).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoPeligro })]));
});

test("una fila de Historial NO lleva relleno completo (sigue la regla general de D-03)", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockImplementation((estado?: string) =>
    Promise.resolve(estado === "recientes" ? [{ id: 2, tipo_display: "Incendio", estado: "resuelta", estado_display: "Resuelta" } as any] : [])
  );
  await render(<ListaAlertasScreen />);
  const fila = await screen.findByTestId("fila-historial-0");
  const estilo = [fila.props.style].flat();
  expect(estilo).not.toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoPeligro })]));
});
