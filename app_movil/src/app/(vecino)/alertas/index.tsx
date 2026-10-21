import { useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { listarAlertas, AlertaOut } from "@/api/alertas";
import { colores } from "@/theme/colores";

export default function ListaAlertasScreen() {
  const router = useRouter();
  const [activas, setActivas] = useState<AlertaOut[]>([]);
  const [historial, setHistorial] = useState<AlertaOut[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Hallazgo I8 de la revisión final: sin .catch, un error de red acá
    // quedaba como un rechazo sin manejar en vez de mostrar algo.
    listarAlertas("activa")
      .then(setActivas)
      .catch(() => setError("No se pudieron cargar las alertas."));
    listarAlertas("recientes")
      .then(setHistorial)
      .catch(() => setError("No se pudieron cargar las alertas."));
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
      {error && <Text style={styles.error}>{error}</Text>}
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
  error: { color: "#b00020", textAlign: "center", marginBottom: 8 },
});
