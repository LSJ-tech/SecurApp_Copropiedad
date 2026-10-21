import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { BotonPanico } from "@/components/BotonPanico";
import { SelectorTipoAlerta } from "@/components/SelectorTipoAlerta";
import { VentanaCancelar } from "@/components/VentanaCancelar";
import { enviarAlerta } from "@/alertas/enviarAlerta";
import { obtenerUbicacionActual } from "@/ubicacion/gps";

export default function PantallaPanico() {
  const [tipo, setTipo] = useState("otro");
  const [alertaEnviadaId, setAlertaEnviadaId] = useState<number | null>(null);

  async function manejarConfirmar(tipoConfirmado: string) {
    const ubicacion = await obtenerUbicacionActual();
    const resultado = await enviarAlerta(
      tipoConfirmado,
      ubicacion?.latitud ?? null,
      ubicacion?.longitud ?? null
    );
    if ("id" in resultado) {
      setAlertaEnviadaId(resultado.id);
    }
  }

  return (
    <View style={styles.container}>
      <BotonPanico onConfirmar={manejarConfirmar} tipoSeleccionado={tipo} />
      <SelectorTipoAlerta valor={tipo} onCambiar={setTipo} />
      {alertaEnviadaId !== null && (
        <VentanaCancelar alertaId={alertaEnviadaId} onCancelada={() => setAlertaEnviadaId(null)} />
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
});
