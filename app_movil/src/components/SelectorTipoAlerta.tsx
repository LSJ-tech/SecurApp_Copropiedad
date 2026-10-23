import { useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, View } from "react-native";

import { TIPOS_ALERTA } from "@/alertas/tipos";
import { colores } from "@/theme/colores";

type Props = {
  valor: string;
  onCambiar: (tipo: string) => void;
};

export function SelectorTipoAlerta({ valor, onCambiar }: Readonly<Props>) {
  const [abierto, setAbierto] = useState(false);
  const actual = TIPOS_ALERTA.find((t) => t.valor === valor);

  return (
    <View>
      <Pressable testID="selector-tipo-abrir" style={styles.control} onPress={() => setAbierto(true)}>
        <Text style={styles.controlTexto}>{actual?.etiqueta ?? "Otro"}</Text>
      </Pressable>
      <Modal visible={abierto} transparent animationType="fade" onRequestClose={() => setAbierto(false)}>
        <Pressable style={styles.fondo} onPress={() => setAbierto(false)}>
          <View style={styles.lista}>
            <FlatList
              data={TIPOS_ALERTA}
              keyExtractor={(item) => item.valor}
              renderItem={({ item }) => (
                <Pressable
                  style={styles.opcion}
                  onPress={() => {
                    onCambiar(item.valor);
                    setAbierto(false);
                  }}
                >
                  <Text>{item.etiqueta}</Text>
                </Pressable>
              )}
            />
          </View>
        </Pressable>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  control: {
    borderWidth: 1,
    borderColor: colores.slate,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
  },
  controlTexto: { color: colores.primary },
  fondo: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", padding: 24 },
  lista: { backgroundColor: "#fff", borderRadius: 12, maxHeight: "60%" },
  opcion: { padding: 16, borderBottomWidth: 1, borderBottomColor: "#eee" },
});
