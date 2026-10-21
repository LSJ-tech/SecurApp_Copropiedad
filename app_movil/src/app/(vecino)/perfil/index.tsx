import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { actualizarMiPerfil, obtenerMiPerfil } from "@/api/auth";
import { ErrorDeServidor } from "@/api/client";
import { colores } from "@/theme/colores";

function primerMensajeDeError(error: unknown): string {
  if (error instanceof ErrorDeServidor && error.body && typeof error.body === "object") {
    const primero = Object.values(error.body as Record<string, unknown>)[0];
    if (Array.isArray(primero) && typeof primero[0] === "string") return primero[0];
  }
  return "No se pudo guardar. Probá de nuevo.";
}

export default function PantallaPerfil() {
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [telefono, setTelefono] = useState("");

  useEffect(() => {
    obtenerMiPerfil()
      .then((perfil) => {
        setFirstName(perfil.first_name ?? "");
        setLastName(perfil.last_name ?? "");
        setEmail(perfil.email ?? "");
        setTelefono(perfil.telefono);
        setCargando(false);
      })
      .catch(() => {
        setError("No se pudo cargar tu perfil.");
        setCargando(false);
      });
  }, []);

  async function manejarGuardar() {
    setError(null);
    try {
      await actualizarMiPerfil({ first_name: firstName, last_name: lastName, email, telefono });
    } catch (error) {
      setError(primerMensajeDeError(error));
    }
  }

  if (cargando) return null;

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      <TextInput style={styles.input} placeholder="Nombre" value={firstName} onChangeText={setFirstName} />
      <TextInput style={styles.input} placeholder="Apellido" value={lastName} onChangeText={setLastName} />
      <TextInput
        style={styles.input}
        placeholder="Correo"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
      />
      <TextInput style={styles.input} placeholder="Teléfono" value={telefono} onChangeText={setTelefono} />
      <Pressable style={styles.boton} onPress={manejarGuardar}>
        <Text style={styles.botonTexto}>Guardar</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  error: { color: "#b00020", textAlign: "center" },
});
