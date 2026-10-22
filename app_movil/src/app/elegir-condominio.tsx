import { useEffect, useRef, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, View } from "react-native";

import { listarCondominiosDevquad, CondominioResumen } from "@/api/devquad";
import { useAuth } from "@/auth/AuthContext";
import { colores } from "@/theme/colores";

export default function ElegirCondominioScreen() {
  const { elegirCondominio, cerrarSesion } = useAuth();
  const [condominios, setCondominios] = useState<CondominioResumen[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Entrar dos veces al mismo condominio no duplica nada del lado del
  // servidor, pero dos requests superpuestas sí podrían pisarse los
  // tokens guardados -- se ignoran toques mientras hay una en curso.
  const eligiendoRef = useRef(false);

  useEffect(() => {
    listarCondominiosDevquad()
      .then(setCondominios)
      .catch(() => setError("No se pudieron cargar los condominios."));
  }, []);

  async function manejarElegir(id: number) {
    if (eligiendoRef.current) return;
    eligiendoRef.current = true;
    setError(null);
    try {
      await elegirCondominio(id);
    } catch {
      setError("No se pudo entrar a ese condominio. Probá de nuevo.");
    } finally {
      eligiendoRef.current = false;
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>Elegí un condominio</Text>
      {error && <Text style={styles.error}>{error}</Text>}
      {/* Hallazgo Important de la revisión final: al borrar
          sin-membresia.tsx, devquad se quedó sin ninguna forma de
          cerrar sesión -- un teléfono prestado/compartido no podía
          salir. También resuelve el caso borde de elegirCondominio
          quedando "atascado" si el refresh usado quedó invalidado a
          mitad de camino (cerrarSesion siempre limpia los tokens
          locales, aunque el aviso al servidor falle). */}
      <Pressable onPress={cerrarSesion} style={styles.cerrarSesion}>
        <Text style={styles.cerrarSesionTexto}>Cerrar sesión</Text>
      </Pressable>
      <FlatList
        data={condominios}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <Pressable style={styles.fila} onPress={() => manejarElegir(item.id)}>
            <Text style={styles.nombre}>{item.nombre}</Text>
          </Pressable>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  titulo: { fontSize: 20, fontWeight: "700", color: colores.primary, marginBottom: 16 },
  fila: { padding: 14, borderBottomWidth: 1, borderBottomColor: "#eee" },
  nombre: { fontWeight: "600" },
  error: { color: "#b00020", textAlign: "center", marginBottom: 8 },
  cerrarSesion: { alignSelf: "flex-end", marginBottom: 16 },
  cerrarSesionTexto: { color: colores.slate, textDecorationLine: "underline" },
});
