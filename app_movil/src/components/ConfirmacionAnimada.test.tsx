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

test("si la vibración falla, no queda un rechazo sin manejar", async () => {
  // Hallazgo Minor de la revisión final: el test anterior solo probaba
  // que el texto se pintara (pasa en el primer render, antes de que
  // corra el effect que llama a Haptics) -- no probaba que el .catch
  // realmente atrapara el rechazo.
  const manejador = jest.fn();
  process.on("unhandledRejection", manejador);
  jest.spyOn(Haptics, "notificationAsync").mockRejectedValue(new Error("no linked"));
  await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
  await new Promise((resolve) => setImmediate(resolve));
  process.off("unhandledRejection", manejador);
  expect(manejador).not.toHaveBeenCalled();
});

test("si se desmonta mientras tanto, limpia el timer pendiente", async () => {
  // Hallazgo Minor de la revisión final: antes solo probaba que
  // unmount() no tirara -- desde React 18 ya no existe el warning de
  // "setState on unmounted component", así que eso pasaría igual sin el
  // clearTimeout del cleanup. jest.getTimerCount() prueba el cleanup de
  // verdad.
  const setTimeoutSpy = jest.spyOn(global, "setTimeout");
  const clearTimeoutSpy = jest.spyOn(global, "clearTimeout");
  const { unmount } = await render(<ConfirmacionAnimada titulo="Alerta enviada" />);
  await screen.findByText("Alerta enviada");
  // Filtra por el delay exacto (4500ms, DURACION_MS en el componente) en
  // vez de asumir que es la primera llamada global a setTimeout -- este
  // entorno de test puede tener timers ajenos al componente de por medio.
  const indice = setTimeoutSpy.mock.calls.findIndex((llamada) => llamada[1] === 4500);
  expect(indice).toBeGreaterThanOrEqual(0);
  const idDelTemporizador = setTimeoutSpy.mock.results[indice].value;
  await act(async () => {
    unmount();
  });
  expect(clearTimeoutSpy).toHaveBeenCalledWith(idDelTemporizador);
});
