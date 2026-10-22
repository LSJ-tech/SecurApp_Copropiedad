import { createContext, useContext, useEffect, useState, ReactNode } from "react";

import { login as loginApi, logout as logoutApi, obtenerMiPerfil, MembresiaOut } from "../api/auth";
import { alSesionExpirada, ErrorDeServidor } from "../api/client";
import { entrarCondominio } from "../api/devquad";
import { registrarDispositivoPush } from "../notificaciones/push";
import { borrarTokens, guardarTokens, obtenerTokens } from "./storage";

type Estado =
  | "cargando"
  | "sin_sesion"
  | "autenticado"
  | "devquad_sin_condominio"
  | "devquad_con_condominio";

type AuthContextValue = {
  estado: Estado;
  membresia: MembresiaOut | null;
  condominioActivo: { id: number; nombre: string } | null;
  iniciarSesion(username: string, password: string): Promise<void>;
  cerrarSesion(): Promise<void>;
  elegirCondominio(id: number): Promise<void>;
  volverAElegirCondominio(): void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>("cargando");
  const [membresia, setMembresia] = useState<MembresiaOut | null>(null);
  const [condominioActivo, setCondominioActivo] = useState<{ id: number; nombre: string } | null>(null);

  useEffect(() => {
    let vigente = true;

    (async () => {
      let tokens: { access: string; refresh: string } | null = null;
      try {
        tokens = await obtenerTokens();
      } catch {
        tokens = null;
      }
      if (!tokens) {
        if (vigente) setEstado("sin_sesion");
        return;
      }
      // No basta con que haya tokens guardados -- hay que confirmar
      // contra el backend quién es (hallazgo I1: una cuenta devquad que
      // cierra y reabre la app no debe caer en la pantalla de pánico con
      // membresia=null, tiene que caer en sin-membresia de verdad).
      try {
        const perfil = await obtenerMiPerfil();
        if (!vigente) return;
        setMembresia(perfil);
        setEstado("autenticado");
        registrarDispositivoPush().catch(() => {});
      } catch (error) {
        if (!vigente) return;
        if (error instanceof ErrorDeServidor && error.status === 409) {
          setEstado("devquad_sin_condominio");
        } else {
          // Sesión realmente vencida, o un error de red/timeout al
          // confirmar -- en ningún caso se debe quedar en "cargando"
          // para siempre (pantalla en blanco).
          setEstado("sin_sesion");
        }
      }
    })().catch(() => {});

    return () => {
      vigente = false;
    };
  }, []);

  useEffect(() => {
    alSesionExpirada(() => {
      setMembresia(null);
      setEstado("sin_sesion");
    });
    return () => alSesionExpirada(null);
  }, []);

  async function iniciarSesion(username: string, password: string) {
    const resultado = await loginApi(username, password);
    await guardarTokens(resultado.access, resultado.refresh);
    setMembresia(resultado.membresia);
    setEstado(resultado.membresia ? "autenticado" : "devquad_sin_condominio");
    if (resultado.membresia) {
      // Sin await a propósito -- no bloquea el login si el permiso de
      // push tarda o el usuario lo niega (ver registrarDispositivoPush).
      // El catch es necesario: sin red o con el backend caído, esto no
      // debe tirar un unhandled rejection ni, mucho menos, el login.
      registrarDispositivoPush().catch(() => {});
    }
  }

  async function elegirCondominio(id: number) {
    const tokens = await obtenerTokens();
    if (!tokens) throw new Error("No hay sesión activa.");
    const resultado = await entrarCondominio(id, tokens.refresh);
    await guardarTokens(resultado.access, resultado.refresh);
    setCondominioActivo({ id: resultado.condominio.id, nombre: resultado.condominio.nombre });
    setEstado("devquad_con_condominio");
  }

  function volverAElegirCondominio() {
    // No borra tokens -- devquad sigue con la misma sesión, solo elige
    // otro condominio (entrarCondominio emite un refresh nuevo cada vez).
    setCondominioActivo(null);
    setEstado("devquad_sin_condominio");
  }

  async function cerrarSesion() {
    // Sin esto, el refresh seguía siendo válido en el servidor hasta
    // por 30 días (REFRESH_TOKEN_LIFETIME) después de un "logout" --
    // un teléfono perdido podía seguir refrescando la sesión.
    const tokens = await obtenerTokens();
    if (tokens) {
      // Sin red, no hay forma de avisarle al backend -- pero el
      // residente tiene que poder salir de su propia sesión igual.
      await logoutApi(tokens.refresh).catch(() => {});
    }
    await borrarTokens();
    setMembresia(null);
    setCondominioActivo(null);
    setEstado("sin_sesion");
  }

  return (
    <AuthContext.Provider
      value={{
        estado,
        membresia,
        condominioActivo,
        iniciarSesion,
        cerrarSesion,
        elegirCondominio,
        volverAElegirCondominio,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const valor = useContext(AuthContext);
  if (!valor) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return valor;
}
