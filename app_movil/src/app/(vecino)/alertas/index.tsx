import { useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { listarAlertas, AlertaOut } from "@/api/alertas";
import { colores } from "@/theme/colores";

export default function ListaAlertasScreen() {
  const router = useRouter();
  const [activas, setActivas] = useState<AlertaOut[]>([]);
  const [historial, setHistorial] = useState<AlertaOut[]>([]);

  useEffect(() => {
    listarAlertas("activa").then(setActivas);
    listarAlertas("recientes").then(setHistorial);
  }, []);

  function Fila({ item }: { item: AlertaOut }) {
    return (
      <Pressable style={styles.fila} onPress={() => router.push(`/alertas/${item.id}`)}>
        <Text style={styles.filaTitulo}>{item.tipo_display}</Text>
        <Text style={styles.filaSubtitulo}>{item.estado_display}</Text>
      </Pressable>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.seccion}>Activas</Text>
      <FlatList data={activas} keyExtractor={(a) => String(a.id)} renderItem={Fila} />
      <Text style={styles.seccion}>Historial</Text>
      <FlatList data={historial} keyExtractor={(a) => String(a.id)} renderItem={Fila} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  seccion: { fontSize: 18, fontWeight: "700", color: colores.primary, marginVertical: 8 },
  fila: { padding: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  filaTitulo: { fontWeight: "600" },
  filaSubtitulo: { color: colores.slate },
});
