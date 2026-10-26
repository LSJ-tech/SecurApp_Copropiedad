import { render, screen, within } from "@testing-library/react-native";
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

test("si falla la carga, no muestra 'Todo tranquilo por ahora' -- sería una falsa tranquilidad", async () => {
  // Hallazgo Important de la revisión final: activas/historial arrancan
  // en [] y el error no los limpia, así que con mala señal la pantalla
  // mostraba un error Y, debajo, las dos tarjetas verdes de "todo
  // tranquilo" -- justo el mensaje contrario al que corresponde en una
  // app de seguridad.
  jest.spyOn(alertasApi, "listarAlertas").mockRejectedValue(new ErrorDeRed("sin red"));
  await render(<ListaAlertasScreen />);
  await screen.findByText(/no se pudieron cargar las alertas/i);
  expect(screen.queryByTestId("tarjeta-sin-activas")).toBeNull();
  expect(screen.queryByTestId("tarjeta-sin-historial")).toBeNull();
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

test("sin alertas activas, muestra una tarjeta positiva (D-02: también en esta pestaña, no solo en la principal)", async () => {
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([]);
  await render(<ListaAlertasScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-sin-activas");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoPositivo })])
  );
  await within(tarjeta).findByText(/todo tranquilo por ahora/i);
});

test("historial vacío muestra el estado vacío ilustrado, no queda en blanco", async () => {
  // Hallazgo Important de la revisión final: "Todo tranquilo por ahora"
  // en Historial es engañoso -- un historial vacío no significa que no
  // haya alertas activas (eso lo dice la sección Activas, no esta), así
  // que no es un color/mensaje de "buena noticia" sino informativo.
  jest.spyOn(alertasApi, "listarAlertas").mockResolvedValue([]);
  await render(<ListaAlertasScreen />);
  const tarjeta = await screen.findByTestId("tarjeta-sin-historial");
  expect(tarjeta.props.style).toEqual(
    expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.fondoInfo })])
  );
  await within(tarjeta).findByText(/sin alertas resueltas en las últimas 24 h/i);
});
