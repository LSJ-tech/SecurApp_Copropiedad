import { useEffect, useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";

import { listarDirectorio, MiembroDirectorio } from "@/api/directorio";
import { ErrorDeServidor } from "@/api/client";
import { colores } from "@/theme/colores";

export default function DirectorioScreen() {
  const [miembros, setMiembros] = useState<MiembroDirectorio[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listarDirectorio()
      .then(setMiembros)
      .catch((error) => {
        if (error instanceof ErrorDeServidor && error.status === 403) {
          setError("No tienes acceso al directorio.");
        } else {
          setError("No se pudo cargar el directorio.");
        }
      });
  }, []);

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <FlatList
        data={miembros}
        keyExtractor={(item, indice) => `${item.nombre}-${indice}`}
        renderItem={({ item, index }) => (
          <View testID={`fila-directorio-${index}`} style={styles.fila}>
            <Text style={styles.nombre}>{item.nombre}</Text>
            {(item.torre || item.unidad) && (
              <Text style={styles.unidad}>
                {[item.torre, item.unidad].filter(Boolean).join(" - ")}
              </Text>
            )}
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  // Acento (borde lateral), nunca relleno completo -- una lista larga de
  // vecinos no debe volverse muchos bloques de color repetidos (D-03).
  fila: { paddingVertical: 10, paddingLeft: 10, borderLeftWidth: 3, borderLeftColor: colores.primary, marginBottom: 6 },
  nombre: { fontWeight: "600", color: colores.primary },
  unidad: { color: colores.slate },
  error: { color: colores.peligro, textAlign: "center", marginBottom: 8 },
});
