import { apiFetch } from "./client";

export type NumeroEmergenciaOut = {
  id: number;
  categoria: string;
  categoria_display: string;
  nombre: string;
  telefono: string;
  es_nacional: boolean;
};

export type PropuestaOut = {
  id: number;
  categoria: string;
  categoria_display: string;
  nombre: string;
  telefono: string;
  nota: string;
  estado: "pendiente" | "aprobada" | "rechazada";
  estado_display: string;
  fecha_creacion: string;
};

export function listarNumerosEmergencia(): Promise<NumeroEmergenciaOut[]> {
  return apiFetch<NumeroEmergenciaOut[]>("/api/v1/numeros-emergencia/");
}

export function listarMisPropuestas(): Promise<PropuestaOut[]> {
  return apiFetch<PropuestaOut[]>("/api/v1/propuestas-numero-emergencia/");
}

export function proponerNumero(payload: {
  categoria: string;
  nombre: string;
  telefono: string;
  nota?: string;
}): Promise<PropuestaOut> {
  return apiFetch<PropuestaOut>("/api/v1/propuestas-numero-emergencia/", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
