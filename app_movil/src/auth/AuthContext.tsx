import { createContext, useContext, useEffect, useState, ReactNode } from "react";

import { login as loginApi, MembresiaOut } from "../api/auth";
import { borrarTokens, guardarTokens, obtenerTokens } from "./storage";

type Estado = "cargando" | "sin_sesion" | "sin_membresia" | "autenticado";

type AuthContextValue = {
  estado: Estado;
  membresia: MembresiaOut | null;
  iniciarSesion(username: string, password: string): Promise<void>;
  cerrarSesion(): Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [estado, setEstado] = useState<Estado>("cargando");
  const [membresia, setMembresia] = useState<MembresiaOut | null>(null);

  useEffect(() => {
    obtenerTokens().then((tokens) => {
      setEstado(tokens ? "autenticado" : "sin_sesion");
    });
  }, []);

  async function iniciarSesion(username: string, password: string) {
    const resultado = await loginApi(username, password);
    await guardarTokens(resultado.access, resultado.refresh);
    setMembresia(resultado.membresia);
    setEstado(resultado.membresia ? "autenticado" : "sin_membresia");
  }

  async function cerrarSesion() {
    await borrarTokens();
    setMembresia(null);
    setEstado("sin_sesion");
  }

  return (
    <AuthContext.Provider value={{ estado, membresia, iniciarSesion, cerrarSesion }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const valor = useContext(AuthContext);
  if (!valor) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return valor;
}
