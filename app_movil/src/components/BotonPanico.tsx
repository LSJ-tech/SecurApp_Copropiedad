import { useRef } from "react";
import { Animated, Pressable, StyleSheet, Text } from "react-native";

const DURACION_CONFIRMACION_MS = 2000;

type Props = {
  onConfirmar: (tipo: string) => void;
  tipoSeleccionado: string;
};

export function BotonPanico({ onConfirmar, tipoSeleccionado }: Readonly<Props>) {
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Sin esto no había ninguna señal de cuánto faltaba para los 2
  // segundos -- hallazgo real probando en un dispositivo real.
  const progreso = useRef(new Animated.Value(0)).current;

  function manejarPressIn() {
    progreso.setValue(0);
    Animated.timing(progreso, {
      toValue: 1,
      duration: DURACION_CONFIRMACION_MS,
      useNativeDriver: false,
    }).start();
    temporizador.current = setTimeout(() => {
      onConfirmar(tipoSeleccionado);
    }, DURACION_CONFIRMACION_MS);
  }

  function manejarPressOut() {
    if (temporizador.current) {
      clearTimeout(temporizador.current);
      temporizador.current = null;
    }
    progreso.stopAnimation();
    progreso.setValue(0);
  }

  const anchoProgreso = progreso.interpolate({ inputRange: [0, 1], outputRange: ["0%", "100%"] });

  return (
    <Pressable
      testID="boton-panico"
      style={styles.boton}
      onPressIn={manejarPressIn}
      onPressOut={manejarPressOut}
    >
      <Animated.View testID="boton-panico-progreso" style={[styles.progreso, { width: anchoProgreso }]} />
      <Text style={styles.texto}>⚠ Mantén presionado{"\n"}2 segundos</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  boton: {
    width: "100%",
    paddingVertical: 18,
    paddingHorizontal: 16,
    backgroundColor: "#b00020",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 16,
    overflow: "hidden",
    elevation: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
  },
  progreso: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    backgroundColor: "rgba(255,255,255,0.25)",
  },
  texto: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
});
