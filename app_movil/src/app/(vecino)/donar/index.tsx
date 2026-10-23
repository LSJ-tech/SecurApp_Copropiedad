import { useEffect, useState } from "react";
import * as Linking from "expo-linking";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { cancelarDonacion, crearDonacion, obtenerMiDonacion, MiDonacion } from "@/api/donaciones";
import { mensajeDetalleDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

// Monto fijo -- no lo elige quien dona, igual que en el panel web
// (pagos/views.py MONTO_DONACION).
const MONTO_DONACION_TEXTO = "$2.000";

export default function DonarScreen() {
  const [datos, setDatos] = useState<MiDonacion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  function cargar() {
    obtenerMiDonacion()
      .then(setDatos)
      .catch(() => setError("No se pudo cargar tu donación."));
  }

  useEffect(cargar, []);

  async function manejarDonar() {
    setError(null);
    setProcesando(true);
    try {
      const resultado = await crearDonacion();
      // Navegador externo a propósito -- evita el régimen de In-App
      // Purchase de Apple/Google (donación voluntaria, no desbloquea
      // nada dentro de la app).
      await Linking.openURL(resultado.url_autorizacion);
    } catch (error) {
      setError(mensajeDetalleDeError(error, "No pudimos iniciar la donación. Probá de nuevo."));
    } finally {
      setProcesando(false);
    }
  }

  async function manejarCancelar() {
    setError(null);
    setProcesando(true);
    try {
      await cancelarDonacion();
      cargar();
    } catch (error) {
      setError(mensajeDetalleDeError(error, "No pudimos cancelar la donación. Probá de nuevo."));
    } finally {
      setProcesando(false);
    }
  }

  if (!datos) return null;

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      {datos.donacion_actual ? (
        <>
          <Text style={styles.titulo}>Tu donación</Text>
          <Text>Estado: {datos.donacion_actual.estado}</Text>
          <Text>Monto mensual: ${datos.donacion_actual.monto}</Text>
          <Pressable style={styles.boton} onPress={manejarCancelar} disabled={procesando}>
            <Text style={styles.botonTexto}>Cancelar</Text>
          </Pressable>
        </>
      ) : (
        <>
          <Text style={styles.titulo}>Apoyá a Mi Barrio+</Text>
          <Text>Donación mensual automática de {MONTO_DONACION_TEXTO}</Text>
          <Pressable style={styles.boton} onPress={manejarDonar} disabled={procesando}>
            <Text style={styles.botonTexto}>Donar</Text>
          </Pressable>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  titulo: { fontSize: 18, fontWeight: "700", color: colores.primary },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  error: { color: "#b00020", textAlign: "center" },
});
