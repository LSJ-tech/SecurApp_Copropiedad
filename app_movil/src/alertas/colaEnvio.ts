import AsyncStorage from "@react-native-async-storage/async-storage";

import { crearAlerta } from "../api/alertas";

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

export async function encolarAlerta(payload: AlertaPendiente): Promise<void> {
  const cola = await leerCola();
  cola.push(payload);
  await escribirCola(cola);
}

export async function procesarCola(): Promise<void> {
  let cola = await leerCola();
  while (cola.length > 0) {
    const [siguiente, ...resto] = cola;
    try {
      await crearAlerta(siguiente);
    } catch {
      // No reordena: se detiene en el primer fallo y reintenta desde acá
      // la próxima vez que se llame a procesarCola().
      return;
    }
    cola = resto;
    await escribirCola(cola);
  }
}
