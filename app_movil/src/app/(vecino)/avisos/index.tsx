import { useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { crearAviso, listarAvisos, marcarLeido, AvisoOut } from "@/api/avisos";
import { useAuth } from "@/auth/AuthContext";
import { colores } from "@/theme/colores";

export default function ListaAvisosScreen() {
  const { membresia } = useAuth();
  const [avisos, setAvisos] = useState<AvisoOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");
  const [cuerpo, setCuerpo] = useState("");

  useEffect(() => {
    listarAvisos()
      .then((lista) => {
        setAvisos(lista);
        // Pasivo a propósito -- mismo comportamiento que
        // core/templates/core/inicio.html: es informativo para devquad
        // (cuántos vecinos vieron un aviso), no un reaseguro personal
        // como "visto por" en Alertas (D-05), que sí exige una acción
        // explícita. Si falla marcar uno, no rompe la lista ya mostrada.
        lista.forEach((aviso) => marcarLeido(aviso.id).catch(() => {}));
      })
      .catch(() => setError("No se pudieron cargar los avisos."));
  }, []);

  async function manejarPublicar() {
    try {
      const nuevo = await crearAviso({ titulo, cuerpo });
      setAvisos((previos) => [nuevo, ...previos]);
      setTitulo("");
      setCuerpo("");
    } catch {
      setError("No se pudo publicar el aviso.");
    }
  }

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}

      {membresia?.rol === "delegado" && (
        <View style={styles.formulario}>
          <TextInput
            style={styles.input}
            placeholder="Título"
            value={titulo}
            onChangeText={setTitulo}
          />
          <TextInput
            style={styles.input}
            placeholder="Mensaje"
            value={cuerpo}
            onChangeText={setCuerpo}
            multiline
          />
          <Pressable style={styles.boton} onPress={manejarPublicar}>
            <Text style={styles.botonTexto}>Publicar aviso</Text>
          </Pressable>
        </View>
      )}

      <FlatList
        data={avisos}
        keyExtractor={(a) => String(a.id)}
        renderItem={({ item }) => (
          <View style={styles.tarjeta}>
            <Text style={styles.titulo}>{item.titulo}</Text>
            <Text style={styles.meta}>
              {new Date(item.fecha_creacion).toLocaleString()} — {item.autor_nombre ?? "DevQuad"}
            </Text>
            <Text>{item.cuerpo}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  formulario: { gap: 8, marginBottom: 16 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 12, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  tarjeta: { paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  titulo: { fontWeight: "700", color: colores.primary },
  meta: { fontSize: 12, color: colores.slate, marginBottom: 4 },
  error: { color: "#b00020", textAlign: "center", marginBottom: 8 },
});
