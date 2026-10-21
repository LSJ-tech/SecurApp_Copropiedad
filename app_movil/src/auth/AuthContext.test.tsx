import { act, render, screen, waitFor } from "@testing-library/react-native";
import { Text } from "react-native";
import { AuthProvider, useAuth } from "./AuthContext";
import * as authApi from "../api/auth";
import * as storage from "./storage";

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
  await act(() => auth!.cerrarSesion());
  expect(borrarSpy).toHaveBeenCalled();
  await waitFor(() => expect(auth.estado).toBe("sin_sesion"));
});
