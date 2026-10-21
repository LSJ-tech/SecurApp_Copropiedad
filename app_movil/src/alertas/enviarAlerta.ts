import { crearAlerta, AlertaOut } from "../api/alertas";
import { ErrorDeRed } from "../api/client";
import { encolarAlerta } from "./colaEnvio";

export async function enviarAlerta(
  tipo: string,
  latitud: number | null,
  longitud: number | null
): Promise<AlertaOut | { encolada: true }> {
  try {
    return await crearAlerta({ tipo, latitud, longitud });
  } catch (error) {
    if (!(error instanceof ErrorDeRed)) {
      // No es un fallo transitorio de red -- encolarlo lo dejaría
      // bloqueando la cola para siempre (ver colaEnvio.ts). Se propaga
      // para que la pantalla lo muestre de verdad.
      throw error;
    }
    await encolarAlerta({ tipo, latitud, longitud });
    return { encolada: true };
  }
}
