import { useEffect, useRef } from "react";
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

  // Sin esto, si el componente se desmonta mientras la animación sigue
  // corriendo (ej. soltar nunca llega a dispararse en un confirmar
  // exitoso), el frame pendiente podía terminar de ejecutarse después,
  // disparando sobre un entorno ya desmontado/destruido -- se vio como
  // "Exceeded timeout"/"accessed after the Jest environment was torn
  // down" en los tests.
  useEffect(() => {
    return () => progreso.stopAnimation();
  }, [progreso]);

  function manejarPressIn() {
    progreso.setValue(0);
    Animated.timing(progreso, {
      toValue: 1,
      duration: DURACION_CONFIRMACION_MS,
      // Nativo (transform, no width): corre en el hilo nativo sin
      // disparar un re-render de React en cada frame -- con
      // useNativeDriver: false, cada uno de esos re-renders durante los
      // tests (que avanzan el reloj falso de un salto) quedaba fuera de
      // act() y a veces dejaba un callback pendiente que intentaba
      // correr después de que Jest ya había desmontado el entorno.
      useNativeDriver: true,
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

  const escalaProgreso = progreso.interpolate({ inputRange: [0, 1], outputRange: [0, 1] });

  return (
    <Pressable
      testID="boton-panico"
      style={styles.boton}
      onPressIn={manejarPressIn}
      onPressOut={manejarPressOut}
    >
      <Animated.View
        testID="boton-panico-progreso"
        style={[styles.progreso, { transform: [{ scaleX: escalaProgreso }] }]}
      />
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
    right: 0,
    backgroundColor: "rgba(255,255,255,0.25)",
    transformOrigin: "left",
  },
  texto: {
    color: "#fff",
    fontSize: 16,
    fontWeight: "700",
    textAlign: "center",
  },
});
