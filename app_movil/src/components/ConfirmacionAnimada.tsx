import { useEffect, useRef, useState } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as Haptics from "expo-haptics";

import { colores } from "@/theme/colores";

// Cuánto queda visible antes de retirarse sola -- independiente de que
// el residente cancele la alerta o no (VentanaCancelar tiene su propio
// ciclo de vida, separado de este).
const DURACION_MS = 4500;

type Props = {
  titulo: string;
  subtitulo?: string;
};

export function ConfirmacionAnimada({ titulo, subtitulo }: Readonly<Props>) {
  const [visible, setVisible] = useState(true);
  const opacidad = useRef(new Animated.Value(0)).current;
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    Animated.timing(opacidad, { toValue: 1, duration: 300, useNativeDriver: true }).start();
    temporizador.current = setTimeout(() => setVisible(false), DURACION_MS);
    return () => {
      opacidad.stopAnimation();
      if (temporizador.current) {
        clearTimeout(temporizador.current);
        temporizador.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!visible) return null;

  return (
    <Animated.View testID="confirmacion-animada" style={[styles.tarjeta, { opacity: opacidad }]}>
      <View style={styles.circulo}>
        <Ionicons name="checkmark" size={16} color="#fff" />
      </View>
      <View style={styles.texto}>
        <Text style={styles.titulo}>{titulo}</Text>
        {subtitulo && <Text style={styles.subtitulo}>{subtitulo}</Text>}
      </View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  tarjeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    backgroundColor: colores.fondoPositivo,
    borderRadius: 12,
    padding: 12,
    width: "100%",
  },
  circulo: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colores.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  texto: { flexShrink: 1 },
  titulo: { fontWeight: "700", color: colores.primary },
  subtitulo: { color: colores.secondary },
});
