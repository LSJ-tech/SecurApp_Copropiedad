import { useEffect, useState } from "react";
import * as Linking from "expo-linking";
import { AppState, Pressable, StyleSheet, Text, View } from "react-native";

import { cancelarDonacion, crearDonacion, obtenerMiDonacion, MiDonacion } from "@/api/donaciones";
import { mensajeDetalleDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

// Monto fijo -- no lo elige quien dona, igual que en el panel web
// (pagos/views.py MONTO_DONACION).
const MONTO_DONACION_TEXTO = "$2.000";

// Monto sin decimales (coherente con MONTO_DONACION_TEXTO), con "." como
// separador de miles -- evita depender de Intl/toLocaleString, que en
// Hermes (runtime real del teléfono) no siempre trae datos ICU completos.
function formatearMonto(valorStr: string): string {
  const entero = Math.round(parseFloat(valorStr)).toString();
  return entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

// Mismo criterio que usan los propios endpoints del backend (pagos/api_views.py):
// donar/cancelar aceptan "pendiente" o "autorizada" -- cualquier otro
// estado (o ninguna donación) es elegible para donar de nuevo. Hallazgo
// Critical de la revisión final: antes se decidía solo por "¿hay
// donacion_actual?", así que una donación cancelada o pausada dejaba a
// la persona viendo "Cancelar" para siempre, sin forma de volver a donar.
const ESTADOS_CANCELABLES = new Set(["pendiente", "autorizada"]);

export default function DonarScreen() {
  const [datos, setDatos] = useState<MiDonacion | null>(null);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [procesando, setProcesando] = useState(false);

  function cargar() {
    setErrorCarga(null);
    obtenerMiDonacion()
      .then(setDatos)
      .catch(() => setErrorCarga("No se pudo cargar tu donación."));
  }

  useEffect(cargar, []);

  useEffect(() => {
    // Volver del navegador externo (tras autorizar en Mercado Pago) pasa
    // por acá -- sin esto, la pantalla se queda con los datos de antes
    // de donar hasta que se reinicie la app entera (hallazgo Important
    // de la revisión final).
    const suscripcion = AppState.addEventListener("change", (estado) => {
      if (estado === "active") cargar();
    });
    return () => suscripcion.remove();
  }, []);

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

  if (errorCarga) {
    return (
      <View style={styles.container}>
        <Text style={styles.error}>{errorCarga}</Text>
        <Pressable style={styles.boton} onPress={cargar}>
          <Text style={styles.botonTexto}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  if (!datos) return null;

  const esCancelable = datos.donacion_actual && ESTADOS_CANCELABLES.has(datos.donacion_actual.estado);

  return (
    <View style={styles.container}>
      {error && <Text style={styles.error}>{error}</Text>}
      {esCancelable ? (
        <>
          <Text style={styles.titulo}>Tu donación</Text>
          <Text>Estado: {datos.donacion_actual!.estado}</Text>
          <Text>Monto mensual: ${datos.donacion_actual!.monto}</Text>
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

      <Text style={styles.titulo}>Historial</Text>
      {datos.pagos.length === 0 ? (
        <Text>Todavía no tienes donaciones registradas.</Text>
      ) : (
        <>
          <Text>
            Has aportado ${formatearMonto(datos.total_donado)} en {datos.cantidad_aportes} aporte
            {datos.cantidad_aportes === 1 ? "" : "s"}.
          </Text>
          {datos.pagos.map((pago, indice) => (
            <Text key={indice}>
              {pago.fecha_creacion.slice(0, 10)} · ${formatearMonto(pago.monto)} · {pago.estado}
            </Text>
          ))}
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
