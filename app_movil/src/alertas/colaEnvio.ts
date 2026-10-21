import { AppState } from "react-native";
import AsyncStorage from "@react-native-async-storage/async-storage";

import { crearAlerta } from "../api/alertas";
import { ErrorDeRed, SesionExpiradaError } from "../api/client";

const CLAVE_COLA = "mibarrio.colaAlertas";

type AlertaPendiente = {
  tipo: string;
  mensaje?: string;
  latitud?: number | null;
  longitud?: number | null;
};

async function leerCola(): Promise<AlertaPendiente[]> {
  const bruto = await AsyncStorage.getItem(CLAVE_COLA);
  return bruto ? JSON.parse(bruto) : [];
}

async function escribirCola(cola: AlertaPendiente[]): Promise<void> {
  await AsyncStorage.setItem(CLAVE_COLA, JSON.stringify(cola));
}

// Serializa todo acceso de lectura-modificación-escritura a la cola --
// encolarAlerta() y procesarCola() pueden correr "al mismo tiempo" (ej.
// una segunda alerta real mientras la primera todavía se está
// reintentando) y sin esto una escritura podía pisar a la otra
// (hallazgo I3 de la revisión final).
let colaEnTurno: Promise<unknown> = Promise.resolve();
function conTurno<T>(tarea: () => Promise<T>): Promise<T> {
  const resultado = colaEnTurno.then(tarea, tarea);
  colaEnTurno = resultado.catch(() => {});
  return resultado;
}

export async function encolarAlerta(payload: AlertaPendiente): Promise<void> {
  await conTurno(async () => {
    const cola = await leerCola();
    cola.push(payload);
    await escribirCola(cola);
  });
}

let procesando = false;

export async function procesarCola(): Promise<void> {
  if (procesando) return;
  procesando = true;
  try {
    while (true) {
      const siguiente = await conTurno(async () => {
        const cola = await leerCola();
        return cola[0] ?? null;
      });
      if (!siguiente) return;

      try {
        await crearAlerta(siguiente);
      } catch (error) {
        if (error instanceof ErrorDeRed || error instanceof SesionExpiradaError) {
          // Transitorio, o no es culpa de ESTA alerta (la sesión expiró
          // a mitad de camino) -- se detiene sin tocar la cola, se
          // reintenta la próxima vez que se llame a procesarCola().
          return;
        }
        // No transitorio (4xx/5xx real): reintentarlo no lo va a
        // arreglar. Se descarta ESE item (no toda la cola) para no
        // bloquear a los que vienen detrás para siempre (hallazgo I2).
      }

      await conTurno(async () => {
        // Siempre se saca el primero: nada más que esta función saca
        // items de la cola (procesando=true evita 2 procesarCola a la
        // vez), así que el que sigue siendo cabeza es el que se acaba
        // de procesar -- comparar por contenido fallaría igual si dos
        // alertas pendientes tienen exactamente los mismos campos.
        const cola = await leerCola();
        await escribirCola(cola.slice(1));
      });
    }
  } finally {
    procesando = false;
  }
}

/** Conecta la cola a algo real: la procesa una vez al llamarse (por si
 * quedó algo pendiente de una sesión anterior) y de nuevo cada vez que
 * la app vuelve a primer plano -- "mientras la app sigue viva" (D-04 #2)
 * no alcanza si nada la vuelve a intentar (hallazgo C1 de la revisión
 * final: antes, nada llamaba nunca a procesarCola() en producción).
 * Devuelve una función para dejar de escuchar (usada al desmontar). */
export function iniciarProcesamientoAutomatico(): () => void {
  procesarCola();
  const suscripcion = AppState.addEventListener("change", (estado) => {
    if (estado === "active") procesarCola();
  });
  return () => suscripcion.remove();
}
