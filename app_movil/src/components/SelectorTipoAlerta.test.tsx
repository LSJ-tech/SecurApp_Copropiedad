import { render, fireEvent, screen } from "@testing-library/react-native";
import { SelectorTipoAlerta } from "./SelectorTipoAlerta";
import { colores } from "@/theme/colores";

test("al elegir un tipo de la grilla, llama a onCambiar con ese valor", async () => {
  // Hallazgo real probando en el emulador: el modal se sentía
  // desconectado del resto de la pantalla -- pasa a ser una grilla
  // siempre visible, sin paso extra para verla.
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await fireEvent.press(screen.getByText("Incendio"));
  expect(onCambiar).toHaveBeenCalledWith("incendio");
});

test("la grilla muestra los tipos con ícono, no una lista de texto plana", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await screen.findByTestId("grilla-tipos-alerta");
  expect(screen.getByTestId("icono-tipo-robo").props.name).toBe("shield-outline");
  expect(screen.getByTestId("icono-tipo-incendio").props.name).toBe("flame-outline");
});

test("cada opción tiene rol y etiqueta de accesibilidad", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="incendio" onCambiar={onCambiar} />);
  const opcion = screen.getByTestId("opcion-tipo-incendio");
  expect(opcion.props.accessibilityRole).toBe("button");
  expect(opcion.props.accessibilityLabel).toMatch(/incendio/i);
  expect(opcion.props.accessibilityLabel).toMatch(/seleccionado/i);
  expect(screen.getByTestId("opcion-tipo-robo").props.accessibilityLabel).not.toMatch(/seleccionado/i);
});

test("el tipo actualmente seleccionado se resalta en la grilla", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="incendio" onCambiar={onCambiar} />);
  const opcionIncendio = await screen.findByTestId("opcion-tipo-incendio");
  const opcionRobo = screen.getByTestId("opcion-tipo-robo");
  const estiloIncendio = [opcionIncendio.props.style].flat();
  const estiloRobo = [opcionRobo.props.style].flat();
  expect(estiloIncendio).toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.peligro })]));
  expect(estiloRobo).not.toEqual(expect.arrayContaining([expect.objectContaining({ backgroundColor: colores.peligro })]));
});

test("muestra una etiqueta que deja claro qué es esta sección", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await screen.findByText(/tipo de emergencia/i);
});

test("la grilla es una vista que envuelve en wrap, no una lista virtualizada anidada en el scroll de la pantalla", async () => {
  // Hallazgo real probando el build en el emulador: un FlatList
  // virtualizado anidado dentro del ScrollView de la pantalla no
  // medía bien su ancho -- quedaba encogido a una caja angosta y
  // centrada en vez de ocupar el ancho completo, con el texto de
  // cada opción cortado. Una grilla simple (View + flexWrap) se
  // estira igual que cualquier otro elemento de la pantalla.
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  const grilla = await screen.findByTestId("grilla-tipos-alerta");
  const estilo = [grilla.props.style].flat();
  expect(estilo).toEqual(expect.arrayContaining([expect.objectContaining({ flexWrap: "wrap" })]));
});
