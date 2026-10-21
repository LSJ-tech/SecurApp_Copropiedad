import { apiFetch } from "./client";

export function registrarDispositivo(token: string, plataforma: "ios" | "android"): Promise<void> {
  return apiFetch<void>("/api/v1/dispositivos/", {
    method: "POST",
    body: JSON.stringify({ token, plataforma }),
  });
}
