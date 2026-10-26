import type { ComponentProps } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { colores } from "@/theme/colores";

type Props = {
  icono: ComponentProps<typeof Ionicons>["name"];
  mensaje: string;
  testID?: string;
};

export function EstadoVacioIlustrado({ icono, mensaje, testID }: Readonly<Props>) {
  return (
    <View testID={testID} style={styles.contenedor}>
      <Ionicons testID={testID ? `${testID}-icono` : undefined} name={icono} size={40} color={colores.accent} />
      <Text style={styles.mensaje}>{mensaje}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { alignItems: "center", gap: 6, paddingVertical: 6 },
  mensaje: { color: colores.secondary, textAlign: "center" },
});
