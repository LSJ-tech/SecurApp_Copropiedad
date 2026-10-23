import { useRef } from "react";
import { Pressable, StyleSheet, Text } from "react-native";

import { colores } from "@/theme/colores";

const DURACION_CONFIRMACION_MS = 2000;

type Props = {
  onConfirmar: (tipo: string) => void;
  tipoSeleccionado: string;
};

export function BotonPanico({ onConfirmar, tipoSeleccionado }: Readonly<Props>) {
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null);

  function manejarPressIn() {
    temporizador.current = setTimeout(() => {
      onConfirmar(tipoSeleccionado);
    }, DURACION_CONFIRMACION_MS);
  }

  function manejarPressOut() {
    if (temporizador.current) {
      clearTimeout(temporizador.current);
      temporizador.current = null;
    }
  }

  return (
    <Pressable
      testID="boton-panico"
      style={styles.boton}
      onPressIn={manejarPressIn}
      onPressOut={manejarPressOut}
    >
      <Text style={styles.texto}>Mantén presionado{"\n"}2 segundos</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  boton: {
    width: 220,
    height: 220,
    borderRadius: 110,
    backgroundColor: colores.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  texto: {
    color: "#fff",
    fontSize: 18,
    fontWeight: "700",
    textAlign: "center",
  },
});
