import { crearAlerta, AlertaOut } from "../api/alertas";
import { encolarAlerta } from "./colaEnvio";

export async function enviarAlerta(
  tipo: string,
  latitud: number | null,
  longitud: number | null
): Promise<AlertaOut | { encolada: true }> {
  try {
    return await crearAlerta({ tipo, latitud, longitud });
  } catch {
    await encolarAlerta({ tipo, latitud, longitud });
    return { encolada: true };
  }
}
