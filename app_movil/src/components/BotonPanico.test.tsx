import { render, fireEvent, screen } from "@testing-library/react-native";
import { BotonPanico } from "./BotonPanico";

test("mantener apretado 2000ms confirma con el tipo seleccionado", async () => {
  const onConfirmar = jest.fn();
  await render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="otro" />);
  jest.useFakeTimers();
  await fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  await jest.advanceTimersByTimeAsync(2000);
  jest.useRealTimers();
  expect(onConfirmar).toHaveBeenCalledWith("otro");
});

test("soltar antes de 2000ms no confirma nada", async () => {
  const onConfirmar = jest.fn();
  await render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="otro" />);
  const boton = screen.getByTestId("boton-panico");
  jest.useFakeTimers();
  await fireEvent(boton, "pressIn");
  await jest.advanceTimersByTimeAsync(1000);
  await fireEvent(boton, "pressOut");
  await jest.advanceTimersByTimeAsync(2000);
  jest.useRealTimers();
  expect(onConfirmar).not.toHaveBeenCalled();
});

test("mientras se mantiene presionado, se ve la barra de progreso", async () => {
  // Hallazgo real probando en el emulador: no había ninguna señal de
  // cuánto faltaba para los 2 segundos -- la barra le da esa referencia.
  const onConfirmar = jest.fn();
  await render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="otro" />);
  const boton = screen.getByTestId("boton-panico");
  await fireEvent(boton, "pressIn");
  expect(screen.getByTestId("boton-panico-progreso")).toBeTruthy();
});

test("usa el tipo pasado por prop, no siempre 'otro'", async () => {
  const onConfirmar = jest.fn();
  await render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="incendio" />);
  jest.useFakeTimers();
  await fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  await jest.advanceTimersByTimeAsync(2000);
  jest.useRealTimers();
  expect(onConfirmar).toHaveBeenCalledWith("incendio");
});
