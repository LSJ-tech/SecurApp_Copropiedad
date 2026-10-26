import { render, fireEvent, screen } from "@testing-library/react-native";
import { SelectorTipoAlerta } from "./SelectorTipoAlerta";

test("al elegir un tipo de la lista, llama a onCambiar con ese valor", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await fireEvent.press(screen.getByTestId("selector-tipo-abrir"));
  await fireEvent.press(screen.getByText("Incendio"));
  expect(onCambiar).toHaveBeenCalledWith("incendio");
});

test("muestra una etiqueta que deja claro que se puede elegir el tipo de emergencia", async () => {
  // Hallazgo real probando en el emulador: el control se veía igual que
  // un campo de texto deshabilitado, así que no se notaba que era
  // tocable -- el label y la flecha lo dejan claro de un vistazo.
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await screen.findByText(/tipo de emergencia/i);
});
