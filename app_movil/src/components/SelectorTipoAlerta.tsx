import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { TIPOS_ALERTA } from "@/alertas/tipos";
import { ICONO_POR_TIPO } from "@/alertas/iconosTipo";
import { colores } from "@/theme/colores";

type Props = {
  valor: string;
  onCambiar: (tipo: string) => void;
};

export function SelectorTipoAlerta({ valor, onCambiar }: Readonly<Props>) {
  return (
    <View style={styles.contenedor}>
      <Text style={styles.etiqueta}>Tipo de emergencia</Text>
      <FlatList
        testID="grilla-tipos-alerta"
        data={TIPOS_ALERTA}
        numColumns={3}
        scrollEnabled={false}
        keyExtractor={(item) => item.valor}
        renderItem={({ item }) => {
          const seleccionado = item.valor === valor;
          return (
            <Pressable
              testID={`opcion-tipo-${item.valor}`}
              style={[styles.opcion, seleccionado && styles.opcionSeleccionada]}
              onPress={() => onCambiar(item.valor)}
              accessibilityRole="button"
              accessibilityLabel={`${item.etiqueta}${seleccionado ? ", seleccionado" : ""}`}
            >
              <Ionicons
                testID={`icono-tipo-${item.valor}`}
                name={ICONO_POR_TIPO[item.valor]}
                size={24}
                color={seleccionado ? "#fff" : colores.peligro}
              />
              <Text style={[styles.opcionTexto, seleccionado && styles.opcionTextoSeleccionado]}>
                {item.etiqueta}
              </Text>
            </Pressable>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { paddingHorizontal: 16, paddingVertical: 12, gap: 8 },
  etiqueta: { fontSize: 12, color: colores.secondary, fontWeight: "600", textAlign: "center" },
  opcion: {
    flex: 1 / 3,
    margin: 4,
    aspectRatio: 1,
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    padding: 6,
    borderWidth: 1,
    borderColor: colores.peligro,
    borderRadius: 10,
  },
  opcionSeleccionada: { backgroundColor: colores.peligro },
  opcionTexto: { fontSize: 12, textAlign: "center", color: colores.peligro },
  opcionTextoSeleccionado: { color: "#fff" },
});
