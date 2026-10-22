import { apiFetch } from "./client";

export type Torre = {
  id: number;
  nombre: string;
};

export function listarTorres(): Promise<Torre[]> {
  return apiFetch<Torre[]>("/api/v1/torres/");
}

export function crearTorre(nombre: string): Promise<Torre> {
  return apiFetch<Torre>("/api/v1/torres/", {
    method: "POST",
    body: JSON.stringify({ nombre }),
  });
}
