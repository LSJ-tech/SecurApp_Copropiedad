import { render, fireEvent, screen } from "@testing-library/react-native";
import { SelectorTipoAlerta } from "./SelectorTipoAlerta";

test("al elegir un tipo de la lista, llama a onCambiar con ese valor", async () => {
  const onCambiar = jest.fn();
  await render(<SelectorTipoAlerta valor="otro" onCambiar={onCambiar} />);
  await fireEvent.press(screen.getByTestId("selector-tipo-abrir"));
  await fireEvent.press(screen.getByText("Incendio"));
  expect(onCambiar).toHaveBeenCalledWith("incendio");
});
