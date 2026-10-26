import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { useAuth } from "@/auth/AuthContext";
import { ErrorDeRed } from "@/api/client";
import { colores } from "@/theme/colores";

export default function LoginScreen() {
  const { iniciarSesion } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function manejarEnviar() {
    setError(null);
    setEnviando(true);
    try {
      await iniciarSesion(username, password);
    } catch (error) {
      // Hallazgo real: un catch genérico mostraba "Usuario o contraseña
      // incorrectos." aunque el problema fuera la conexión -- hacía
      // dudar de la contraseña a un residente sin señal.
      setError(error instanceof ErrorDeRed ? "No se pudo conectar. Revisa tu conexión." : "Usuario o contraseña incorrectos.");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <View style={styles.container}>
      <Text style={styles.titulo}>Mi Barrio+</Text>
      <TextInput
        style={styles.input}
        placeholder="Usuario"
        autoCapitalize="none"
        value={username}
        onChangeText={setUsername}
      />
      <TextInput
        style={styles.input}
        placeholder="Contraseña"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />
      {error && <Text style={styles.error}>{error}</Text>}
      <Pressable style={styles.boton} onPress={manejarEnviar} disabled={enviando}>
        <Text style={styles.botonTexto}>{enviando ? "Ingresando..." : "Ingresar"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", padding: 24, gap: 12 },
  titulo: { fontSize: 28, fontWeight: "700", color: colores.primary, textAlign: "center", marginBottom: 24 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  error: { color: "#b00020" },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
});
