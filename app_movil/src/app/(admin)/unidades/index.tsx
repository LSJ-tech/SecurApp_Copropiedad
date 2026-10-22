import { useEffect, useState } from "react";
import { FlatList, Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { crearUnidad, listarUnidades, Unidad } from "@/api/unidades";
import { listarTorres, Torre } from "@/api/torres";
import { primerMensajeDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

export default function UnidadesScreen() {
  const [unidades, setUnidades] = useState<Unidad[]>([]);
  const [torres, setTorres] = useState<Torre[]>([]);
  const [numero, setNumero] = useState("");
  const [torreElegida, setTorreElegida] = useState<Torre | null>(null);
  const [selectorAbierto, setSelectorAbierto] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listarUnidades()
      .then(setUnidades)
      .catch(() => setError("No se pudieron cargar las unidades."));
    listarTorres().then(setTorres).catch(() => {});
  }, []);

  async function manejarAgregar() {
    setError(null);
    try {
      const payload: { numero: string; torre?: number } = { numero };
      if (torreElegida) payload.torre = torreElegida.id;
      const nueva = await crearUnidad(payload);
      setUnidades((previas) => [...previas, nueva]);
      setNumero("");
      setTorreElegida(null);
    } catch (error) {
      setError(primerMensajeDeError(error));
    }
  }

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <View style={styles.formulario}>
        <TextInput style={styles.input} placeholder="Número" value={numero} onChangeText={setNumero} />
        <Pressable style={styles.selector} onPress={() => setSelectorAbierto(true)}>
          <Text>{torreElegida?.nombre ?? "Sin torre"}</Text>
        </Pressable>
        <Pressable style={styles.boton} onPress={manejarAgregar}>
          <Text style={styles.botonTexto}>Agregar</Text>
        </Pressable>
      </View>
      <Modal visible={selectorAbierto} transparent animationType="fade" onRequestClose={() => setSelectorAbierto(false)}>
        <Pressable style={styles.fondo} onPress={() => setSelectorAbierto(false)}>
          <View style={styles.lista}>
            <FlatList
              data={torres}
              keyExtractor={(t) => String(t.id)}
              renderItem={({ item }) => (
                <Pressable
                  style={styles.opcion}
                  onPress={() => {
                    setTorreElegida(item);
                    setSelectorAbierto(false);
                  }}
                >
                  <Text>{item.nombre}</Text>
                </Pressable>
              )}
            />
          </View>
        </Pressable>
      </Modal>
      <FlatList
        data={unidades}
        keyExtractor={(u) => String(u.id)}
        renderItem={({ item }) => {
          // Hallazgo Important de la revisión final: Empart (cliente real)
          // repite números de unidad entre torres distintas -- sin el
          // nombre de la torre son indistinguibles en la lista.
          const torreNombre = torres.find((t) => t.id === item.torre)?.nombre;
          return (
            <View style={styles.fila}>
              <Text>{torreNombre ? `${item.numero} · ${torreNombre}` : item.numero}</Text>
            </View>
          );
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16 },
  formulario: { flexDirection: "row", gap: 8, marginBottom: 16, alignItems: "center" },
  input: { flex: 1, borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  selector: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 12, justifyContent: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  fila: { padding: 12, borderBottomWidth: 1, borderBottomColor: "#eee" },
  error: { color: "#b00020", textAlign: "center", marginBottom: 8 },
  fondo: { flex: 1, backgroundColor: "rgba(0,0,0,0.4)", justifyContent: "center", padding: 24 },
  lista: { backgroundColor: "#fff", borderRadius: 12, maxHeight: "60%" },
  opcion: { padding: 16, borderBottomWidth: 1, borderBottomColor: "#eee" },
});
