jest.mock("expo-notifications", () => ({
  getPermissionsAsync: jest.fn().mockResolvedValue({ status: "granted" }),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn().mockResolvedValue({ data: "ExponentPushToken[test]" }),
}));

import { act, render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";
import { AuthProvider, useAuth } from "./AuthContext";
import * as authApi from "../api/auth";
import * as storage from "./storage";
import * as dispositivosApi from "../api/dispositivos";
import { apiFetch, ErrorDeRed, ErrorDeServidor } from "../api/client";

afterEach(() => {
  jest.restoreAllMocks();
});

function Sonda() {
  const { estado, membresia } = useAuth();
  return <Text>{estado}:{membresia?.nombre ?? "-"}</Text>;
}

test("sin tokens guardados, arranca en sin_sesion", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  await act(async () => {
    render(
      <AuthProvider>
        <Sonda />
      </AuthProvider>
    );
  });
  await waitFor(() => screen.getByText("sin_sesion:-"));
});

test("login exitoso con membresia pasa a autenticado", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  jest.spyOn(authApi, "login").mockResolvedValue({
    access: "a",
    refresh: "r",
    membresia: {
      nombre: "Ana",
      rol: "residente",
      condominio: { id: 1, nombre: "X" },
      unidad: null,
      telefono: "",
    },
  });
  let auth: ReturnType<typeof useAuth>;
  function Capturador() {
    auth = useAuth();
    return null;
  }
  await act(async () => {
    render(
      <AuthProvider>
        <Capturador />
      </AuthProvider>
    );
  });
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
  await act(() => auth!.iniciarSesion("ana", "clave"));
  await waitFor(() => expect(auth.estado).toBe("autenticado"));
  expect(auth!.membresia?.nombre).toBe("Ana");
});

test("login exitoso con membresia dispara el registro de push (sin bloquear la UI)", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  jest.spyOn(authApi, "login").mockResolvedValue({
    access: "a",
    refresh: "r",
    membresia: {
      nombre: "Ana",
      rol: "residente",
      condominio: { id: 1, nombre: "X" },
      unidad: null,
      telefono: "",
    },
  });
  const registrarSpy = jest.spyOn(dispositivosApi, "registrarDispositivo").mockResolvedValue();
  let auth: ReturnType<typeof useAuth>;
  function Capturador() {
    auth = useAuth();
    return null;
  }
  await act(async () => {
    render(
      <AuthProvider>
        <Capturador />
      </AuthProvider>
    );
  });
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
  await act(() => auth!.iniciarSesion("ana", "clave"));
  await waitFor(() => expect(auth.estado).toBe("autenticado"));
  expect(registrarSpy).toHaveBeenCalled();
});

test("login exitoso sin membresia (devquad) pasa a sin_membresia, no a autenticado", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue(null);
  jest.spyOn(storage, "guardarTokens").mockResolvedValue();
  jest.spyOn(authApi, "login").mockResolvedValue({ access: "a", refresh: "r", membresia: null });
  let auth: ReturnType<typeof useAuth>;
  function Capturador() {
    auth = useAuth();
    return null;
  }
  await act(async () => {
    render(
      <AuthProvider>
        <Capturador />
      </AuthProvider>
    );
  });
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
  await act(() => auth!.iniciarSesion("devquad", "clave"));
  await waitFor(() => expect(auth.estado).toBe("sin_membresia"));
});

test("cerrarSesion borra los tokens guardados y vuelve a sin_sesion", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "a", refresh: "r" });
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    nombre: "Ana",
    rol: "residente",
    condominio: { id: 1, nombre: "X" },
    unidad: null,
    telefono: "",
  });
  const borrarSpy = jest.spyOn(storage, "borrarTokens").mockResolvedValue();
  let auth: ReturnType<typeof useAuth>;
  function Capturador() {
    auth = useAuth();
    return null;
  }
  await act(async () => {
    render(
      <AuthProvider>
        <Capturador />
      </AuthProvider>
    );
  });
  await waitFor(() => expect(auth.estado).toBe("autenticado"));
  const logoutSpy = jest.spyOn(authApi, "logout").mockResolvedValue();
  await act(() => auth!.cerrarSesion());
  expect(logoutSpy).toHaveBeenCalledWith("r");
  expect(borrarSpy).toHaveBeenCalled();
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
});

test("cerrarSesion borra los tokens locales igual aunque el logout contra el servidor falle (sin red)", async () => {
  // El refresh queda sin invalidar en el servidor en ese caso
  // (riesgo aceptado: sin red no hay forma de avisarle al backend),
  // pero el residente tiene que poder salir de su propia sesión igual.
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "a", refresh: "r" });
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    nombre: "Ana",
    rol: "residente",
    condominio: { id: 1, nombre: "X" },
    unidad: null,
    telefono: "",
  });
  const borrarSpy = jest.spyOn(storage, "borrarTokens").mockResolvedValue();
  jest.spyOn(authApi, "logout").mockRejectedValue(new ErrorDeRed("sin red"));
  let auth: ReturnType<typeof useAuth>;
  function Capturador() {
    auth = useAuth();
    return null;
  }
  await act(async () => {
    render(
      <AuthProvider>
        <Capturador />
      </AuthProvider>
    );
  });
  await waitFor(() => expect(auth.estado).toBe("autenticado"));
  await act(() => auth!.cerrarSesion());
  expect(borrarSpy).toHaveBeenCalled();
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
});

test("con tokens guardados, confirma la membresia real contra /auth/me/ al montar (no asume autenticado a ciegas)", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "a", refresh: "r" });
  const perfilSpy = jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    nombre: "Ana",
    rol: "residente",
    condominio: { id: 1, nombre: "X" },
    unidad: null,
    telefono: "",
  });
  await act(async () => {
    render(
      <AuthProvider>
        <Sonda />
      </AuthProvider>
    );
  });
  await waitFor(() => screen.getByText("autenticado:Ana"));
  expect(perfilSpy).toHaveBeenCalled();
});

test("con tokens guardados pero sin membresia (409, cuenta devquad), cae en sin_membresia al reabrir la app", async () => {
  // Hallazgo I1 de la revisión final: antes, reabrir la app con una
  // cuenta devquad caía en la pantalla de pánico (autenticado con
  // membresia=null) en vez de sin-membresia.
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "a", refresh: "r" });
  jest.spyOn(authApi, "obtenerMiPerfil").mockRejectedValue(new ErrorDeServidor(409));
  await act(async () => {
    render(
      <AuthProvider>
        <Sonda />
      </AuthProvider>
    );
  });
  await waitFor(() => screen.getByText("sin_membresia:-"));
});

test("si confirmar la sesion al montar falla por un error de red, no se queda en cargando para siempre", async () => {
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "a", refresh: "r" });
  jest.spyOn(authApi, "obtenerMiPerfil").mockRejectedValue(new ErrorDeRed("sin red"));
  await act(async () => {
    render(
      <AuthProvider>
        <Sonda />
      </AuthProvider>
    );
  });
  await waitFor(() => screen.getByText("sin_sesion:-"));
});

test("cuando se dispara el listener de sesion expirada, pasa a sin_sesion y limpia la membresia", async () => {
  // Hallazgo C3: antes, SesionExpiradaError se lanzaba y se perdía --
  // nadie en la UI reaccionaba, así que el estado seguía "autenticado"
  // con tokens que ya no servían.
  jest.spyOn(storage, "obtenerTokens").mockResolvedValue({ access: "a", refresh: "r" });
  jest.spyOn(authApi, "obtenerMiPerfil").mockResolvedValue({
    nombre: "Ana",
    rol: "residente",
    condominio: { id: 1, nombre: "X" },
    unidad: null,
    telefono: "",
  });
  await act(async () => {
    render(
      <AuthProvider>
        <Sonda />
      </AuthProvider>
    );
  });
  await waitFor(() => screen.getByText("autenticado:Ana"));

  // Dispara el mecanismo real (no un hook de test aparte): una request
  // cualquiera que reciba 401 dos veces seguidas (access vencido Y el
  // refresh también falla) es justo lo que hace que client.ts avise.
  global.fetch = jest.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) }) as any;
  await act(async () => {
    await apiFetch("/api/v1/alertas/").catch(() => {});
  });
  await waitFor(() => screen.getByText("sin_sesion:-"));
});
