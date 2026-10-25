import { useEffect, useRef, useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { BotonPanico } from "@/components/BotonPanico";
import { SelectorTipoAlerta } from "@/components/SelectorTipoAlerta";
import { VentanaCancelar } from "@/components/VentanaCancelar";
import { enviarAlerta } from "@/alertas/enviarAlerta";
import { obtenerUbicacionActual } from "@/ubicacion/gps";
import { useAuth } from "@/auth/AuthContext";
import { obtenerMiDonacion, MiDonacion } from "@/api/donaciones";
import { listarAlertas, AlertaOut } from "@/api/alertas";
import { colores } from "@/theme/colores";

// Monto sin decimales, con "." como separador de miles -- mismo criterio
// que ya usa la pantalla Donar (evita depender de Intl/toLocaleString,
// que en Hermes no siempre trae datos ICU completos).
function formatearMonto(valorStr: string): string {
  const entero = Math.round(parseFloat(valorStr)).toString();
  return entero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

export default function PantallaPanico() {
  const { membresia } = useAuth();
  const router = useRouter();
  const [tipo, setTipo] = useState("otro");
  const [alertaEnviadaId, setAlertaEnviadaId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Ref, no solo estado: la guarda tiene que valer apenas se llama a
  // manejarConfirmar, sin depender de que React ya haya re-renderizado
  // con el estado nuevo (hallazgo I9 de la revisión final -- sin esto,
  // mientras el GPS+POST seguían en curso, un segundo press-and-hold
  // mandaba una segunda alerta real).
  const enviandoRef = useRef(false);

  const [donacion, setDonacion] = useState<MiDonacion | null>(null);
  const [alertasActivas, setAlertasActivas] = useState<AlertaOut[]>([]);

  useEffect(() => {
    // Tarjetas secundarias -- un fallo acá nunca debe bloquear ni tocar
    // el flujo de pánico, por eso cada una atrapa su propio error y
    // simplemente se queda sin datos (la tarjeta no se muestra con
    // información, pero el botón de pánico sigue intacto).
    obtenerMiDonacion().then(setDonacion).catch(() => {});
    listarAlertas("activa").then(setAlertasActivas).catch(() => {});
  }, []);

  async function manejarConfirmar(tipoConfirmado: string) {
    if (enviandoRef.current) return;
    enviandoRef.current = true;
    setError(null);
    try {
      const ubicacion = await obtenerUbicacionActual();
      const resultado = await enviarAlerta(
        tipoConfirmado,
        ubicacion?.latitud ?? null,
        ubicacion?.longitud ?? null
      );
      if ("id" in resultado) {
        setAlertaEnviadaId(resultado.id);
      }
    } catch {
      // No es transitorio (enviarAlerta ya encoló los que sí lo son) --
      // esto es algo que reintentar en silencio no va a arreglar, el
      // residente tiene que saberlo.
      setError("No se pudo mandar la alerta. Probá de nuevo.");
    } finally {
      enviandoRef.current = false;
    }
  }

  const condominio = membresia?.condominio;
  const unidad = membresia?.unidad;
  const etiquetaUnidadMin = condominio?.etiqueta_unidad?.toLowerCase() ?? "unidad";
  const textoUnidad = unidad
    ? `${condominio?.etiqueta_torre ?? ""} ${unidad.torre_nombre ?? "—"}, ${etiquetaUnidadMin} ${unidad.numero}`
    : `Sin ${etiquetaUnidadMin} asignad${condominio?.genero_unidad === "m" ? "o" : "a"}`;

  return (
    <View style={styles.container}>
      <BotonPanico onConfirmar={manejarConfirmar} tipoSeleccionado={tipo} />
      <SelectorTipoAlerta valor={tipo} onCambiar={setTipo} />
      {error && <Text style={styles.error}>{error}</Text>}
      {alertaEnviadaId !== null && (
        <VentanaCancelar
          key={alertaEnviadaId}
          alertaId={alertaEnviadaId}
          onCancelada={() => setAlertaEnviadaId(null)}
        />
      )}

      <ScrollView style={styles.scroll} contentContainerStyle={styles.contenido}>
        <View style={styles.tarjeta}>
          <Text style={styles.tituloTarjeta}>♥ Apoya el proyecto</Text>
          {donacion?.donacion_actual ? (
            <>
              <Text>Donación automática activa: ${formatearMonto(donacion.donacion_actual.monto)}/mes</Text>
              <Pressable style={styles.boton} onPress={() => router.push("/donar")}>
                <Text style={styles.botonTexto}>Ver mi donación</Text>
              </Pressable>
            </>
          ) : (
            <>
              <Text>¿Mi Barrio+ te ha sido útil? Activa una donación automática de $2.000/mes.</Text>
              <Pressable style={styles.boton} onPress={() => router.push("/donar")}>
                <Text style={styles.botonTexto}>Donar</Text>
              </Pressable>
            </>
          )}
        </View>

        <View style={styles.tarjeta}>
          <Text style={styles.tituloTarjeta}>Mi {etiquetaUnidadMin}</Text>
          <Text>{textoUnidad}</Text>
        </View>

        <Pressable style={styles.boton} onPress={() => router.push("/invitar")}>
          <Text style={styles.botonTexto}>Invitar vecinos</Text>
        </Pressable>
        {membresia?.rol === "delegado" && (
          <Pressable style={styles.boton} onPress={() => router.push("/directorio")}>
            <Text style={styles.botonTexto}>Directorio</Text>
          </Pressable>
        )}

        <View style={styles.tarjeta}>
          <Text style={styles.tituloTarjeta}>Alertas activas</Text>
          {alertasActivas.length === 0 ? (
            <Text>Sin alertas activas.</Text>
          ) : (
            alertasActivas.map((a) => (
              <Pressable key={a.id} onPress={() => router.push(`/alertas/${a.id}`)}>
                <Text>{a.tipo_display}</Text>
              </Pressable>
            ))
          )}
        </View>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  scroll: { flex: 1 },
  contenido: { padding: 16, gap: 12 },
  tarjeta: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12, gap: 8 },
  tituloTarjeta: { fontWeight: "700", color: colores.primary },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 12, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  error: { color: "#b00020", textAlign: "center", paddingHorizontal: 24 },
});
