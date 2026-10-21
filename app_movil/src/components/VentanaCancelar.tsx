import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import { resolverAlerta } from "@/api/alertas";
import { colores } from "@/theme/colores";

const DURACION_VENTANA_MS = 10000;

type Props = {
  alertaId: number;
  onCancelada: () => void;
};

export function VentanaCancelar({ alertaId, onCancelada }: Props) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const temporizador = setTimeout(() => setVisible(false), DURACION_VENTANA_MS);
    return () => clearTimeout(temporizador);
  }, []);

  if (!visible) return null;

  async function manejarCancelar() {
    await resolverAlerta(alertaId, "falsa_alarma");
    onCancelada();
  }

  return (
    <Pressable style={styles.boton} onPress={manejarCancelar}>
      <Text style={styles.texto}>Cancelar, fue un error</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  boton: {
    marginTop: 16,
    backgroundColor: colores.secondary,
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 20,
  },
  texto: { color: "#fff", fontWeight: "600" },
});
