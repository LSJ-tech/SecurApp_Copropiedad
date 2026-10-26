import { render, fireEvent, screen } from "@testing-library/react-native";
import { SelectorTipoAlerta } from "./SelectorTipoAlerta";
import { colores } from "@/theme/colores";

test("al elegir un tipo de la lista, llama a onCambiar con ese valor", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await fireEvent.press(screen.getByTestId("selector-tipo-abrir"));
  await fireEvent.press(screen.getByText("Incendio"));
  expect(onCambiar).toHaveBeenCalledWith("incendio");
});

test("el modal muestra los tipos con ícono, no una lista de texto plana", async () => {
  // numColumns es consumido internamente por FlatList/VirtualizedList y
  // nunca se refleja en los props del nodo host -- no verificable por
  // inspección de props (mismo problema que `cancelable` en
  // BotonPanico). Lo observable es que cada opción ahora trae su ícono.
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await fireEvent.press(screen.getByTestId("selector-tipo-abrir"));
  await screen.findByTestId("grilla-tipos-alerta");
  expect(screen.getByTestId("icono-tipo-robo").props.name).toBe("shield-outline");
  expect(screen.getByTestId("icono-tipo-incendio").props.name).toBe("flame-outline");
});

test("el tipo actualmente seleccionado se resalta en la grilla", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="incendio" onCambiar={onCambiar} />);
  await fireEvent.press(screen.getByTestId("selector-tipo-abrir"));
  const opcionIncendio = await screen.findByTestId("opcion-tipo-incendio");
  const opcionRobo = screen.getByTestId("opcion-tipo-robo");
  const estiloIncendio = [opcionIncendio.props.style].flat();
  const estiloRobo = [opcionRobo.props.style].flat();
  expect(estiloIncendio).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.peligro })]));
  expect(estiloRobo).not.toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.peligro })]));
});

test("muestra una etiqueta que deja claro que se puede elegir el tipo de emergencia", async () => {
  // Hallazgo real probando en el emulador: el control se veía igual que
  // un campo de texto deshabilitado, así que no se notaba que era
  // tocable -- el label y la flecha lo dejan claro de un vistazo.
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await screen.findByText(/tipo de emergencia/i);
});
