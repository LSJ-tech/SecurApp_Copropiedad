import { useEffect, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { actualizarMiCondominio, obtenerMiCondominio, regenerarCodigoInvitacion, CondominioEdicion } from "@/api/condominio";
import { primerMensajeDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

export default function PantallaMiCondominio() {
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [errorGuardado, setErrorGuardado] = useState<string | null>(null);
  const [guardadoOk, setGuardadoOk] = useState(false);
  const [codigoNuevo, setCodigoNuevo] = useState<string | null>(null);
  const [datos, setDatos] = useState<CondominioEdicion | null>(null);

  function cargar() {
    setCargando(true);
    setErrorCarga(null);
    obtenerMiCondominio()
      .then((perfil) => {
        setDatos(perfil);
        setCargando(false);
      })
      .catch(() => {
        setErrorCarga("No se pudo cargar tu condominio.");
        setCargando(false);
      });
  }

  useEffect(cargar, []);

  function campo<K extends keyof CondominioEdicion>(clave: K, valor: CondominioEdicion[K]) {
    setDatos((previo) => (previo ? { ...previo, [clave]: valor } : previo));
  }

  async function manejarGuardar() {
    if (!datos) return;
    setErrorGuardado(null);
    setGuardadoOk(false);
    try {
      await actualizarMiCondominio(datos);
      setGuardadoOk(true);
    } catch (error) {
      setErrorGuardado(primerMensajeDeError(error));
    }
  }

  function manejarRegenerar() {
    Alert.alert(
      "¿Regenerar el código de invitación?",
      "El link anterior deja de funcionar.",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Regenerar",
          onPress: async () => {
            try {
              const resultado = await regenerarCodigoInvitacion();
              setCodigoNuevo(resultado.token_registro_residentes);
            } catch (error) {
              setErrorGuardado(primerMensajeDeError(error));
            }
          },
        },
      ]
    );
  }

  if (cargando) return null;

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

  return (
    <View style={styles.container}>
      {errorGuardado && <Text style={styles.error}>{errorGuardado}</Text>}
      {guardadoOk && <Text style={styles.exito}>Tus datos quedaron actualizados.</Text>}
      {codigoNuevo && <Text style={styles.exito}>Nuevo código: {codigoNuevo}</Text>}
      <TextInput style={styles.input} placeholder="Nombre" value={datos.nombre} onChangeText={(v) => campo("nombre", v)} />
      <TextInput style={styles.input} placeholder="Dirección" value={datos.direccion} onChangeText={(v) => campo("direccion", v)} />
      <TextInput style={styles.input} placeholder="Comuna" value={datos.comuna} onChangeText={(v) => campo("comuna", v)} />
      <TextInput style={styles.input} placeholder="Región" value={datos.region} onChangeText={(v) => campo("region", v)} />
      <Pressable style={styles.boton} onPress={manejarGuardar}>
        <Text style={styles.botonTexto}>Guardar</Text>
      </Pressable>
      <Pressable style={styles.botonSecundario} onPress={manejarRegenerar}>
        <Text style={styles.botonSecundarioTexto}>Regenerar código de invitación</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  botonSecundario: { borderWidth: 1, borderColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonSecundarioTexto: { color: colores.primary, fontWeight: "600" },
  error: { color: "#b00020", textAlign: "center" },
  exito: { color: colores.accent, textAlign: "center" },
});
