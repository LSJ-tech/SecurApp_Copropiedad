import { act, render, screen } from "@testing-library/react-native";
import * as Haptics from "expo-haptics";
import { ConfirmacionAnimada } from "./ConfirmacionAnimada";

afterEach(() => {
  jest.restoreAllMocks();
});

test("muestra título y subtítulo al montar", async () => {
  await render(<ConfirmacionAnimada titulo="Alerta enviada" subtitulo="Vecinos notificados" />);
  await screen.findByText("Alerta enviada");
  await screen.findByText("Vecinos notificados");
});

test("sin subtítulo, no revienta y no lo muestra", async () => {
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
});

test("se retira sola pasado el tiempo", async () => {
  jest.useFakeTimers();
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
  await act(async () => {
    await jest.advanceTimersByTimeAsync(5000);
  });
  jest.useRealTimers();
  expect(screen.queryByText("Alerta enviada")).toBeNull();
});

test("llama a la vibración de éxito al montar", async () => {
  const spy = jest.spyOn(Haptics, "notificationAsync").mockResolvedValue();
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  expect(spy).toHaveBeenCalledWith(Haptics.NotificationFeedbackType.Success);
});

test("si la vibración falla, la confirmación visual igual se muestra", async () => {
  jest.spyOn(Haptics, "notificationAsync").mockRejectedValue(new Error("no linked"));
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
});

test("si se desmonta mientras tanto, no revienta ni deja un timer colgado", async () => {
  const { unmount } = await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
  expect(() => unmount()).not.toThrow();
});
