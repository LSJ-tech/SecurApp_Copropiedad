import { useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { Ionicons } from "@expo/vector-icons";

import { TIPOS_ALERTA } from "@/alertas/tipos";
import { ICONO_POR_TIPO } from "@/alertas/iconosTipo";
import { colores } from "@/theme/colores";

type Props = {
  valor: string;
  onCambiar: (tipo: string) => void;
};

export function SelectorTipoAlerta({ valor, onCambiar }: Readonly<Props>) {
  const [abierto, setAbierto] = useState(false);
  const actual = TIPOS_ALERTA.find((t) => t.valor === valor);

  return (
    <View style={styles.contenedor}>
      <Text style={styles.etiqueta}>Tipo de emergencia</Text>
      <Pressable testID="selector-tipo-abrir" style={styles.control} onPress={() => setAbierto(true)}>
        <Text style={styles.controlTexto}>{actual?.etiqueta ?? "Otro"}</Text>
        <Text style={styles.flecha}>▾</Text>
      </Pressable>
      <Modal visible={abierto} transparent animationType="fade" onRequestClose={() => setAbierto(false)}>
        <Pressable style={styles.fondo} onPress={() => setAbierto(false)}>
          <View style={styles.lista}>
            <FlatList
              testID="grilla-tipos-alerta"
              data={TIPOS_ALERTA}
              numColumns={3}
              keyExtractor={(item) => item.valor}
              renderItem={({ item }) => {
                const seleccionado = item.valor === valor;
                return (
                  <Pressable
                    testID={`opcion-tipo-${item.valor}`}
                    style={[styles.opcion, seleccionado && styles.opcionSeleccionada]}
                    onPress={() => {
                      onCambiar(item.valor);
                      setAbierto(false);
                    }}
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
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  contenedor: { paddingHorizontal: 16, paddingVertical: 12, gap: 4 },
  etiqueta: { fontSize: 12, color: colores.secondary, fontWeight: "600" },
  control: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderWidth: 1,
    borderColor: colores.slate,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
  },
  controlTexto: { color: colores.primary, fontWeight: "600" },
  flecha: { color: colores.primary },
  fondo: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", padding: 24 },
  lista: { backgroundColor: "#fff", borderRadius: 12, maxHeight: "70%", padding: 10 },
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
