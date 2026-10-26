import { useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { useRouter } from "expo-router";

import { listarAlertas, AlertaOut } from "@/api/alertas";
import { EstadoVacioIlustrado } from "@/components/EstadoVacioIlustrado";
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

// Extraído del ternario anidado error ? null : lista.length === 0 ? (...) :
// (...) que tenía Sonar (typescript:S3358) -- de paso elimina la
// duplicación entre Activas e Historial, que ya eran casi idénticos.
function SeccionAlertas({
  lista,
  hayError,
  variante,
  testIdTarjeta,
  testIdEstadoVacio,
  mensajeVacio,
  fondoVacio,
  onPress,
}: Readonly<{
  lista: AlertaOut[];
  hayError: boolean;
  variante: VarianteFila;
  testIdTarjeta: string;
  testIdEstadoVacio: string;
  mensajeVacio: string;
  fondoVacio: string;
  onPress: (item: AlertaOut) => void;
}>) {
  if (hayError) return null;
  if (lista.length === 0) {
    return (
      <View testID={testIdTarjeta} style={[styles.tarjeta, { backgroundColor: fondoVacio }]}>
        <EstadoVacioIlustrado testID={testIdEstadoVacio} icono="shield-checkmark-outline" mensaje={mensajeVacio} />
      </View>
    );
  }
  return (
    <FlatList
      data={lista}
      keyExtractor={(a) => String(a.id)}
      renderItem={({ item, index }) => (
        <Fila item={item} variante={variante} indice={index} onPress={() => onPress(item)} />
      )}
    />
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
      <SeccionAlertas
        lista={activas}
        hayError={!!error}
        variante="activa"
        testIdTarjeta="tarjeta-sin-activas"
        testIdEstadoVacio="estado-vacio-alertas-activas"
        mensajeVacio="Todo tranquilo por ahora"
        fondoVacio={colores.fondoPositivo}
        onPress={(item) => router.push(`/alertas/${item.id}`)}
      />
      <Text style={styles.seccion}>Historial</Text>
      <SeccionAlertas
        lista={historial}
        hayError={!!error}
        variante="historial"
        testIdTarjeta="tarjeta-sin-historial"
        testIdEstadoVacio="estado-vacio-alertas-historial"
        mensajeVacio="Sin alertas resueltas en las últimas 24 h"
        fondoVacio={colores.fondoInfo}
        onPress={(item) => router.push(`/alertas/${item.id}`)}
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
  tarjeta: { borderRadius: 14, padding: 12 },
  filaTitulo: { fontWeight: "600" },
  filaSubtitulo: { color: colores.slate },
  error: { color: colores.peligro, textAlign: "center", marginBottom: 8 },
});
