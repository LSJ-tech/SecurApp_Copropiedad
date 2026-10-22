import { useEffect, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { crearTorre, listarTorres, Torre } from "@/api/torres";
import { primerMensajeDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

export default function TorresScreen() {
  const [torres, setTorres] = useState<Torre[]>([]);
  const [nombre, setNombre] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listarTorres()
      .then(setTorres)
      .catch(() => setError("No se pudieron cargar las torres."));
  }, []);

  async function manejarAgregar() {
    setError(null);
    try {
      const nueva = await crearTorre(nombre);
      setTorres((previas) => [...previas, nueva]);
      setNombre("");
    } catch (error) {
      setError(primerMensajeDeError(error));
    }
  }

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <View style={styles.formulario}>
        <TextInput style={styles.input} placeholder="Nombre de la torre" value={nombre} onChangeText={setNombre} />
        <Pressable style={styles.boton} onPress={manejarAgregar}>
          <Text style={styles.botonTexto}>Agregar</Text>
        </Pressable>
      </View>
      <FlatList
        data={torres}
        keyExtractor={(t) => String(t.id)}
        renderItem={({ item }) => (
          <View style={styles.fila}>
            <Text>{item.nombre}</Text>
          </View>
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  formulario: { flexDirection: "row", gap: 8, marginBottom: 16 },
  input: { flex: 1, borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 12, justifyContent: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  fila: { padding: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  error: { color: "#b00020", textAlign: "center", marginBottom: 8 },
});
