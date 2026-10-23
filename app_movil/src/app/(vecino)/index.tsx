import { useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { BotonPanico } from "@/components/BotonPanico";
import { SelectorTipoAlerta } from "@/components/SelectorTipoAlerta";
import { VentanaCancelar } from "@/components/VentanaCancelar";
import { enviarAlerta } from "@/alertas/enviarAlerta";
import { obtenerUbicacionActual } from "@/ubicacion/gps";

export default function PantallaPanico() {
  const [tipo, setTipo] = useState("otro");
  const [alertaEnviadaId, setAlertaEnviadaId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Ref, no solo estado: la guarda tiene que valer apenas se llama a
  // manejarConfirmar, sin depender de que React ya haya re-renderizado
  // con el estado nuevo (hallazgo I9 de la revisión final -- sin esto,
  // mientras el GPS+POST seguían en curso, un segundo press-and-hold
  // mandaba una segunda alerta real).
  const enviandoRef = useRef(false);

  async function manejarConfirmar(tipoConfirmado: string) {
    if (enviandoRef.current) return;
    enviandoRef.current = true;
    setError(null);
    try {
      const ubicacion = await obtenerUbicacionActual();
      const resultado = await enviarAlerta(
        tipoConfirmado,
        ubicacion?.latitud ?? null,
        ubicacion?.longitud ?? null
      );
      if ("id" in resultado) {
        setAlertaEnviadaId(resultado.id);
      }
    } catch {
      // No es transitorio (enviarAlerta ya encoló los que sí lo son) --
      // esto es algo que reintentar en silencio no va a arreglar, el
      // residente tiene que saberlo.
      setError("No se pudo mandar la alerta. Probá de nuevo.");
    } finally {
      enviandoRef.current = false;
    }
  }

  return (
    <View style={styles.container}>
      <BotonPanico onConfirmar={manejarConfirmar} tipoSeleccionado={tipo} />
      <SelectorTipoAlerta valor={tipo} onCambiar={setTipo} />
      {error && <Text style={styles.error}>{error}</Text>}
      {alertaEnviadaId !== null && (
        <VentanaCancelar
          key={alertaEnviadaId}
          alertaId={alertaEnviadaId}
          onCancelada={() => setAlertaEnviadaId(null)}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 24,
    backgroundColor: "#fff",
  },
  error: { color: "#b00020", textAlign: "center", paddingHorizontal: 24 },
});
