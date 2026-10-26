import { render, fireEvent, screen, cleanup } from "@testing-library/react-native";
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
  // Timers falsos + pressOut antes de terminar: sin esto, el setTimeout
  // real de 2s quedaba pendiente después de que el test terminaba
  // (hallazgo Important de la revisión final -- se cruza con el aviso
  // "A worker process has failed to exit gracefully" que arrastraba la
  // suite completa).
  const onConfirmar = jest.fn();
  await render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="otro" />);
  const boton = screen.getByTestId("boton-panico");
  jest.useFakeTimers();
  await fireEvent(boton, "pressIn");
  expect(screen.getByTestId("boton-panico-progreso")).toBeTruthy();
  await fireEvent(boton, "pressOut");
  jest.useRealTimers();
});

// `cancelable={false}` en BotonPanico.tsx: con el botón ahora dentro de
// un ScrollView (D-04), sin esto RN le pasa la respuesta del gesto al
// ScrollView ante un scroll accidental del dedo, cancelando la alerta en
// silencio -- comportamiento documentado de React Native (el prop
// `cancelable` de Pressable), pero `cancelable` se consume de forma
// interna (usePressability) y no se reenvía al elemento nativo
// renderizado, así que no hay forma de verificarlo inspeccionando
// `.props` vía RTL -- se deja como verificación de código, no de test.

test("si el componente se desmonta mientras está presionado, no confirma después", async () => {
  // Sin limpiar también el setTimeout (no solo la animación) al
  // desmontar, un desmontaje en medio de una pulsación mandaba una
  // alerta real más tarde, sobre un componente que ya no existía.
  const onConfirmar = jest.fn();
  await render(<BotonPanico onConfirmar={onConfirmar} tipoSeleccionado="otro" />);
  jest.useFakeTimers();
  await fireEvent(screen.getByTestId("boton-panico"), "pressIn");
  await cleanup();
  await jest.advanceTimersByTimeAsync(2000);
  jest.useRealTimers();
  expect(onConfirmar).not.toHaveBeenCalled();
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
