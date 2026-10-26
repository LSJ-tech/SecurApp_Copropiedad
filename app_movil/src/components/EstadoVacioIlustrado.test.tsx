import { render, screen } from "@testing-library/react-native";
import { EstadoVacioIlustrado } from "./EstadoVacioIlustrado";

test("muestra el ícono y el mensaje dados", async () => {
  await render(<EstadoVacioIlustrado testID="estado-prueba" icono="newspaper-outline" mensaje="Todavía no hay avisos" />);
  expect(screen.getByTestId("estado-prueba-icono").props.name).toBe("newspaper-outline");
  await screen.findByText("Todavía no hay avisos");
});
