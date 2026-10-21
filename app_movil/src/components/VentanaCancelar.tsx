import { useEffect, useRef, useState } from "react";
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
  const [error, setError] = useState<string | null>(null);
  // Ref, no estado: tiene que bloquear el segundo toque ya mismo, sin
  // esperar a que React re-renderice (hallazgo I5 de la revisión final).
  const cancelandoRef = useRef(false);

  useEffect(() => {
    const temporizador = setTimeout(() => setVisible(false), DURACION_VENTANA_MS);
    return () => clearTimeout(temporizador);
  }, []);

  if (!visible) return null;

  async function manejarCancelar() {
    if (cancelandoRef.current) return;
    cancelandoRef.current = true;
    setError(null);
    try {
      await resolverAlerta(alertaId, "falsa_alarma");
      onCancelada();
    } catch {
      setError("No se pudo cancelar. Probá de nuevo.");
      cancelandoRef.current = false;
    }
  }

  return (
    <>
      <Pressable style={styles.boton} onPress={manejarCancelar}>
        <Text style={styles.texto}>Cancelar, fue un error</Text>
      </Pressable>
      {error && <Text style={styles.error}>{error}</Text>}
    </>
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
  error: { color: "#b00020", marginTop: 8, textAlign: "center" },
});
