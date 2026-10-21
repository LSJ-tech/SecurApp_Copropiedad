import { useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useLocalSearchParams } from "expo-router";

import { marcarVisto, obtenerAlerta, AlertaOut } from "@/api/alertas";
import { colores } from "@/theme/colores";

export default function DetalleAlertaScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [alerta, setAlerta] = useState<AlertaOut | null>(null);

  const cargar = useCallback(() => {
    obtenerAlerta(Number(id)).then(setAlerta);
  }, [id]);

  useEffect(() => {
    cargar();
  }, [cargar]);

  if (!alerta) return null;

  async function manejarMarcarVisto() {
    const actualizada = await marcarVisto(Number(id));
    setAlerta(actualizada);
  }

  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>{alerta.tipo_display}</Text>
      <Text style={styles.linea}>Estado: {alerta.estado_display}</Text>
      <Text style={styles.linea}>Reportada por: {alerta.autor_nombre}</Text>
      {alerta.mensaje ? <Text style={styles.linea}>{alerta.mensaje}</Text> : null}

      {alerta.visto_por_count !== null && (
        <Text style={styles.linea}>Visto por {alerta.visto_por_count} vecino(s)</Text>
      )}

      {alerta.visto_por_count === null && alerta.estado === "activa" && (
        <Pressable style={styles.boton} onPress={manejarMarcarVisto}>
          <Text style={styles.botonTexto}>Marcar como visto</Text>
        </Pressable>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 8 },
  titulo: { fontSize: 22, fontWeight: "700", color: colores.primary },
  linea: { fontSize: 16, color: colores.primary },
  boton: { marginTop: 16, backgroundColor: colores.primary, borderRadius: 8, padding: 12, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
});
