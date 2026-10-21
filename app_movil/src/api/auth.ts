import { apiFetch } from "./client";

export type MembresiaOut = {
  rol: string;
  condominio: { id: number; nombre: string; [k: string]: unknown };
  unidad: { numero: string; [k: string]: unknown } | null;
  nombre: string;
  telefono: string;
};

export type LoginOut = {
  access: string;
  refresh: string;
  membresia: MembresiaOut | null;
};

export function login(username: string, password: string): Promise<LoginOut> {
  return apiFetch<LoginOut>(
    "/api/v1/auth/login/",
    { method: "POST", body: JSON.stringify({ username, password }) },
    false
  );
}
