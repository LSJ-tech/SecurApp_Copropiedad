import { useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { listarAlertas, AlertaOut } from "@/api/alertas";
import { colores } from "@/theme/colores";

type VarianteFila = "activa" | "historial";

function Fila({
  item,
  onPress,
  variante,
  indice,
}: Readonly<{ item: AlertaOut; onPress: () => void; variante: VarianteFila; indice: number }>) {
  return (
    <Pressable
      testID={`fila-${variante}-${indice}`}
      style={[styles.fila, variante === "activa" && { backgroundColor: colores.fondoPeligro }]}
      onPress={onPress}
    >
      <Text style={styles.filaTitulo}>{item.tipo_display}</Text>
      <Text style={styles.filaSubtitulo}>{item.estado_display}</Text>
    </Pressable>
  );
}

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

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <Text style={styles.seccion}>Activas</Text>
      <FlatList
        data={activas}
        keyExtractor={(a) => String(a.id)}
        renderItem={({ item, index }) => (
          <Fila item={item} variante="activa" indice={index} onPress={() => router.push(`/alertas/${item.id}`)} />
        )}
      />
      <Text style={styles.seccion}>Historial</Text>
      <FlatList
        data={historial}
        keyExtractor={(a) => String(a.id)}
        renderItem={({ item, index }) => (
          <Fila item={item} variante="historial" indice={index} onPress={() => router.push(`/alertas/${item.id}`)} />
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  seccion: { fontSize: 18, fontWeight: "700", color: colores.primary, marginVertical: 8 },
  // Acento (borde lateral) para Historial, nunca relleno completo -- un
  // historial largo no debe volverse muchos bloques de color repetidos
  // (D-03). "Activas" es la excepción explícita (ver variante "activa"
  // en Fila): normalmente 0-3 ítems, el color es señal de urgencia real.
  fila: { padding: 12, paddingLeft: 10, borderLeftWidth: 3, borderLeftColor: colores.primary, marginBottom: 6, borderRadius: 4 },
  filaTitulo: { fontWeight: "600" },
  filaSubtitulo: { color: colores.slate },
  error: { color: colores.peligro, textAlign: "center", marginBottom: 8 },
});
