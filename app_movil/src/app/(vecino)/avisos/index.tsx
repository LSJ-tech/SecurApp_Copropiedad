import { useEffect, useRef, useState } from "react";
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
  // Hallazgo Important de la revisión final: dos toques seguidos en
  // "Publicar aviso" mandaban el aviso dos veces -- cada uno dispara un
  // push a todo el condominio o torre (notificar_aviso).
  const publicandoRef = useRef(false);

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
    if (publicandoRef.current) return;
    publicandoRef.current = true;
    try {
      const nuevo = await crearAviso({ titulo, cuerpo });
      setAvisos((previos) => [nuevo, ...previos]);
      setTitulo("");
      setCuerpo("");
    } catch {
      setError("No se pudo publicar el aviso.");
    } finally {
      publicandoRef.current = false;
    }
  }

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}

      {membresia?.rol === "delegado" && (
        <View testID="tarjeta-formulario-aviso" style={[styles.formulario, { backgroundColor: colores.fondoInfo }]}>
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
        renderItem={({ item, index }) => (
          <View testID={`fila-aviso-${index}`} style={styles.tarjeta}>
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
  formulario: { gap: 8, marginBottom: 16, borderRadius: 14, padding: 12 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12, backgroundColor: "#fff" },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 12, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  // Acento (borde lateral), nunca relleno completo -- un historial largo
  // de avisos no debe volverse muchos bloques de color repetidos (D-03).
  tarjeta: { paddingVertical: 12, paddingLeft: 10, borderLeftWidth: 3, borderLeftColor: colores.primary, marginBottom: 6 },
  titulo: { fontWeight: "700", color: colores.primary },
  meta: { fontSize: 12, color: colores.slate, marginBottom: 4 },
  error: { color: colores.peligro, textAlign: "center", marginBottom: 8 },
});
