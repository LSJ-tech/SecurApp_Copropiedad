import { Pressable, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/auth/AuthContext";
import { colores } from "@/theme/colores";

export default function SinMembresiaScreen() {
  const { cerrarSesion } = useAuth();

  return (
    <View style={styles.container}>
      <Text style={styles.mensaje}>
        El modo administrador todavía no está disponible en esta versión de la app -- usa el panel
        web en su lugar.
      </Text>
      <Pressable style={styles.boton} onPress={cerrarSesion}>
        <Text style={styles.botonTexto}>Cerrar sesión</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24, gap: 24 },
  mensaje: { fontSize: 16, textAlign: "center", color: colores.primary },
  boton: { backgroundColor: colores.secondary, borderRadius: 8, padding: 14 },
  botonTexto: { color: "#fff", fontWeight: "600" },
});
