import { apiFetch } from "./client";

export type MiembroDirectorio = {
  nombre: string;
  torre: string | null;
  unidad: string | null;
};

export function listarDirectorio(): Promise<MiembroDirectorio[]> {
  return apiFetch<MiembroDirectorio[]>("/api/v1/directorio/");
}
