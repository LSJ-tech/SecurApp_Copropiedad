import { useEffect, useState } from "react";
import { Pressable, Share, StyleSheet, Text, View } from "react-native";

import { obtenerInvitacion } from "@/api/invitacion";
import { colores } from "@/theme/colores";

export default function InvitarScreen() {
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    obtenerInvitacion()
      .then((datos) => setMensaje(datos.mensaje_whatsapp_invitacion))
      .catch(() => setError("No se pudo cargar la invitación."));
  }, []);

  async function manejarCompartir() {
    if (!mensaje) return;
    // Cancelar la hoja de compartir nativa no es un error -- no hay
    // nada que mostrarle al usuario en ese caso.
    await Share.share({ message: mensaje }).catch(() => {});
  }

  if (error) {
    return (
      <View style={styles.container}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {mensaje && <Text style={styles.mensaje}>{mensaje}</Text>}
      <Pressable style={styles.boton} onPress={manejarCompartir}>
        <Text style={styles.botonTexto}>Compartir</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 16 },
  mensaje: { color: colores.primary },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  error: { color: "#b00020", textAlign: "center" },
});
