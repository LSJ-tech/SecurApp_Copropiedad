import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { BotonPanico } from "@/components/BotonPanico";
import { ConfirmacionAnimada } from "@/components/ConfirmacionAnimada";
import { EstadoVacioIlustrado } from "@/components/EstadoVacioIlustrado";
import { SelectorTipoAlerta } from "@/components/SelectorTipoAlerta";
import { VentanaCancelar } from "@/components/VentanaCancelar";
import { alProcesarColaAlerta } from "@/alertas/colaEnvio";
import { enviarAlerta } from "@/alertas/enviarAlerta";
import { obtenerUbicacionActual } from "@/ubicacion/gps";
import { useAuth } from "@/auth/AuthContext";
import { obtenerMiDonacion, formatearMontoDonacion, ESTADOS_DONACION_CANCELABLES, MiDonacion } from "@/api/donaciones";
import { listarAlertas, AlertaOut } from "@/api/alertas";
import { colores } from "@/theme/colores";

// Extraído del ternario anidado (dentro del template literal de
// textoUnidad) que tenía Sonar (typescript:S3358).
function terminacionGenero(generoUnidad: string | undefined): "o" | "a" {
  return generoUnidad === "m" ? "o" : "a";
}

// Extraído del ternario anidado que tenía Sonar (typescript:S3358).
function colorTarjetaAlertasDe(errorAlertas: boolean, hayAlertasActivas: boolean): string {
  if (errorAlertas) return colores.fondoInfo;
  if (hayAlertasActivas) return colores.fondoPeligro;
  return colores.fondoPositivo;
}

// Mismo motivo -- antes era errorAlertas ? (...) : alertasActivas.length
// === 0 ? (...) : (...) dentro del JSX.
function ContenidoTarjetaAlertas({
  errorAlertas,
  alertasActivas,
  onPress,
}: Readonly<{ errorAlertas: boolean; alertasActivas: AlertaOut[]; onPress: (id: number) => void }>) {
  if (errorAlertas) {
    return <Text style={styles.error}>No se pudieron cargar las alertas.</Text>;
  }
  if (alertasActivas.length === 0) {
    return <EstadoVacioIlustrado testID="estado-vacio-alertas-home" icono="shield-checkmark-outline" mensaje="Todo tranquilo por ahora" />;
  }
  return (
    <>
      {alertasActivas.map((a) => (
        <Pressable key={a.id} onPress={() => onPress(a.id)}>
          <Text>{a.tipo_display}</Text>
        </Pressable>
      ))}
    </>
  );
}

export default function PantallaPanico() {
  const { membresia } = useAuth();
  const router = useRouter();
  const [tipo, setTipo] = useState("otro");
  const [alertaEnviadaId, setAlertaEnviadaId] = useState<number | null>(null);
  // Cuando enviarAlerta() no logra conectar, la encola para reintentar y
  // devuelve {encolada: true} (sin id) -- antes eso no disparaba ninguna
  // señal visible, un vecino con mala señal no se enteraba de si su
  // alerta había hecho algo. La clave (timestamp) remonta
  // ConfirmacionAnimada en cada intento, igual que alertaEnviadaId.
  const [claveEncolada, setClaveEncolada] = useState<number | null>(null);
  // Cuando esa alerta encolada finalmente se procesa (procesarCola, en
  // colaEnvio.ts), nada más avisa -- el autor está excluido a propósito
  // de su propio push (notificar_alerta en el backend). Sin este
  // listener, un vecino que ya se movió de pantalla nunca se entera si
  // su alerta en cola terminó mandándose de verdad.
  const [claveColaResuelta, setClaveColaResuelta] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Ref, no solo estado: la guarda tiene que valer apenas se llama a
  // manejarConfirmar, sin depender de que React ya haya re-renderizado
  // con el estado nuevo (hallazgo I9 de la revisión final -- sin esto,
  // mientras el GPS+POST seguían en curso, un segundo press-and-hold
  // mandaba una segunda alerta real).
  const enviandoRef = useRef(false);

  const [donacion, setDonacion] = useState<MiDonacion | null>(null);
  const [alertasActivas, setAlertasActivas] = useState<AlertaOut[]>([]);
  const [errorAlertas, setErrorAlertas] = useState(false);

  const cargarTarjetas = useCallback(() => {
    // Tarjetas secundarias -- un fallo en donación nunca debe bloquear ni
    // tocar el flujo de pánico, por eso atrapa su propio error y
    // simplemente se queda sin datos. Alertas activas sí distingue "sin
    // alertas" de "no se pudo cargar" (hallazgo Important de la revisión
    // final: con mala señal, "Sin alertas activas." le aseguraba al
    // vecino que no pasaba nada).
    obtenerMiDonacion().then(setDonacion).catch(() => {});
    setErrorAlertas(false);
    listarAlertas("activa")
      .then(setAlertasActivas)
      .catch(() => setErrorAlertas(true));
  }, []);

  // El Drawer deja esta pantalla montada al navegar a otra -- sin
  // useFocusEffect (en vez de un useEffect de una sola vez), donar y
  // volver, o que otro vecino dispare una alerta mientras se estaba en
  // otra pestaña, dejaba estas tarjetas desactualizadas hasta reiniciar
  // la app (hallazgo Important de la revisión final).
  useFocusEffect(useCallback(cargarTarjetas, [cargarTarjetas]));

  useEffect(() => {
    alProcesarColaAlerta((evento) => {
      if (evento.tipo === "enviada") {
        setClaveColaResuelta(Date.now());
        cargarTarjetas();
      } else {
        setError("No se pudo mandar la alerta que había quedado en cola.");
      }
    });
    return () => alProcesarColaAlerta(null);
  }, [cargarTarjetas]);

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
        // Si fui yo quien la mandó, la tarjeta de alertas activas tiene
        // que mostrarla sin esperar a la próxima vez que se enfoque la
        // pantalla (hallazgo Important de la revisión final).
        cargarTarjetas();
      } else {
        setClaveEncolada(Date.now());
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

  const primerNombre = membresia?.first_name ?? membresia?.nombre?.split(" ")[0];

  const condominio = membresia?.condominio;
  const unidad = membresia?.unidad;
  const etiquetaUnidadMin = condominio?.etiqueta_unidad?.toLowerCase() ?? "unidad";
  const textoUnidad = unidad
    ? `${condominio?.etiqueta_torre ?? ""} ${unidad.torre_nombre ?? "—"}, ${etiquetaUnidadMin} ${unidad.numero}`
    : `Sin ${etiquetaUnidadMin} asignad${terminacionGenero(condominio?.genero_unidad)}`;

  const hayAlertasActivas = !errorAlertas && alertasActivas.length > 0;
  // Si falló la carga, ni verde ("todo bien") ni rojo (no sabemos si hay
  // una real) -- hallazgo Important de la revisión final: antes
  // !errorAlertas la dejaba en verde igual, contradiciendo el mensaje de
  // error que está justo al lado.
  const colorTarjetaAlertas = colorTarjetaAlertasDe(errorAlertas, hayAlertasActivas);

  return (
    <View style={styles.container}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.contenido}>
        {primerNombre && <Text style={styles.saludo}>Hola, {primerNombre} 👋</Text>}

        <View testID="tarjeta-depto" style={[styles.tarjeta, { backgroundColor: colores.fondoInfo }]}>
          <Text style={styles.tituloTarjeta}>Mi {etiquetaUnidadMin}</Text>
          <Text>{textoUnidad}</Text>
        </View>

        <View testID="tarjeta-donacion" style={[styles.tarjeta, { backgroundColor: colores.fondoApoyo }]}>
          <Text style={styles.tituloTarjeta}>♥ Apoya el proyecto</Text>
          {donacion?.donacion_actual && ESTADOS_DONACION_CANCELABLES.has(donacion.donacion_actual.estado) ? (
            <>
              <Text>Donación automática activa: ${formatearMontoDonacion(donacion.donacion_actual.monto)}/mes</Text>
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

        <View style={styles.bloquePanico}>
          <BotonPanico onConfirmar={manejarConfirmar} tipoSeleccionado={tipo} />
          {error && <Text style={styles.error}>{error}</Text>}
          {alertaEnviadaId !== null && (
            <>
              <ConfirmacionAnimada key={`confirmacion-${alertaEnviadaId}`} titulo="Alerta enviada" subtitulo="Vecinos notificados" />
              <VentanaCancelar
                key={`cancelar-${alertaEnviadaId}`}
                alertaId={alertaEnviadaId}
                onCancelada={() => setAlertaEnviadaId(null)}
              />
            </>
          )}
          {claveEncolada !== null && (
            <ConfirmacionAnimada
              key={`encolada-${claveEncolada}`}
              titulo="Alerta en cola"
              subtitulo="Se enviará apenas vuelva la señal"
            />
          )}
          {claveColaResuelta !== null && (
            <ConfirmacionAnimada
              key={`cola-resuelta-${claveColaResuelta}`}
              titulo="Alerta enviada"
              subtitulo="Vecinos notificados"
            />
          )}
          <SelectorTipoAlerta valor={tipo} onCambiar={setTipo} />
        </View>

        <View
          testID="tarjeta-alertas"
          style={[styles.tarjeta, { backgroundColor: colorTarjetaAlertas }]}
        >
          <Text style={styles.tituloTarjeta}>Alertas activas</Text>
          <ContenidoTarjetaAlertas
            errorAlertas={errorAlertas}
            alertasActivas={alertasActivas}
            onPress={(id) => router.push(`/alertas/${id}`)}
          />
        </View>

        <Pressable testID="tarjeta-invitar" style={[styles.tarjeta, { backgroundColor: colores.fondoApoyo }]} onPress={() => router.push("/invitar")}>
          <Text style={styles.tituloTarjeta}>Invitar vecinos</Text>
        </Pressable>
        {membresia?.rol === "delegado" && (
          <Pressable testID="tarjeta-directorio" style={[styles.tarjeta, { backgroundColor: colores.fondoInfo }]} onPress={() => router.push("/directorio")}>
            <Text style={styles.tituloTarjeta}>Directorio</Text>
          </Pressable>
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#fff" },
  scroll: { flex: 1 },
  contenido: { padding: 16, gap: 12 },
  saludo: { fontSize: 18, fontWeight: "700", color: colores.primary },
  tarjeta: { borderRadius: 14, padding: 12, gap: 8 },
  tituloTarjeta: { fontWeight: "700", color: colores.primary },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 12, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  error: { color: colores.peligro, textAlign: "center", paddingHorizontal: 24 },
  bloquePanico: { alignItems: "center", gap: 10, paddingVertical: 8 },
});
