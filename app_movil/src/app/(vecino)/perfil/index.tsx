import { useEffect, useRef, useState } from "react";
import * as Linking from "expo-linking";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { actualizarMiPerfil, obtenerMiPerfil } from "@/api/auth";
import { API_BASE_URL } from "@/api/client";
import { primerMensajeDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

export default function PantallaPerfil() {
  const [cargando, setCargando] = useState(true);
  // Hallazgo Critical de la revisión final: si la carga inicial falla,
  // el formulario NO se muestra (en vez de mostrarse vacío) -- guardar
  // sobre un formulario vacío borraba nombre/apellido/correo/teléfono
  // reales en el servidor, sin que nada lo avisara.
  const [errorCarga, setErrorCarga] = useState<string | null>(null);
  const [errorGuardado, setErrorGuardado] = useState<string | null>(null);
  const [guardadoOk, setGuardadoOk] = useState(false);
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [telefono, setTelefono] = useState("");
  // Hallazgo real: era la única pantalla con botón de guardar sin esta
  // guarda (avisos, números de emergencia y elegir-condominio ya la
  // tenían) -- dos toques seguidos mandaban dos PATCH.
  const guardandoRef = useRef(false);

  function cargar() {
    setCargando(true);
    setErrorCarga(null);
    obtenerMiPerfil()
      .then((perfil) => {
        setFirstName(perfil.first_name ?? "");
        setLastName(perfil.last_name ?? "");
        setEmail(perfil.email ?? "");
        setTelefono(perfil.telefono);
        setCargando(false);
      })
      .catch(() => {
        setErrorCarga("No se pudo cargar tu perfil.");
        setCargando(false);
      });
  }

  useEffect(cargar, []);

  async function manejarGuardar() {
    if (guardandoRef.current) return;
    guardandoRef.current = true;
    setErrorGuardado(null);
    setGuardadoOk(false);
    try {
      await actualizarMiPerfil({ first_name: firstName, last_name: lastName, email, telefono });
      setGuardadoOk(true);
    } catch (error) {
      setErrorGuardado(primerMensajeDeError(error));
    } finally {
      guardandoRef.current = false;
    }
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

  return (
    <View style={styles.container}>
      {errorGuardado && <Text style={styles.error}>{errorGuardado}</Text>}
      {guardadoOk && <Text style={styles.exito}>Tus datos quedaron actualizados.</Text>}
      <View testID="tarjeta-perfil" style={[styles.tarjeta, { backgroundColor: colores.fondoInfo }]}>
        <TextInput style={styles.input} placeholder="Nombre" value={firstName} onChangeText={setFirstName} />
        <TextInput style={styles.input} placeholder="Apellido" value={lastName} onChangeText={setLastName} />
        <TextInput
          style={styles.input}
          placeholder="Correo"
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          textContentType="emailAddress"
          autoComplete="email"
        />
        <TextInput
          style={styles.input}
          placeholder="Teléfono"
          value={telefono}
          onChangeText={setTelefono}
          keyboardType="phone-pad"
          textContentType="telephoneNumber"
        />
      </View>
      <Pressable style={styles.boton} onPress={manejarGuardar}>
        <Text style={styles.botonTexto}>Guardar</Text>
      </Pressable>
      <Pressable
        style={styles.boton}
        onPress={() => Linking.openURL(`${API_BASE_URL}/mi-perfil/cambiar-contrasena/`)}
      >
        <Text style={styles.botonTexto}>Cambiar contraseña</Text>
      </Pressable>
      <Pressable
        style={styles.boton}
        onPress={() => Linking.openURL(`${API_BASE_URL}/mi-perfil/eliminar-cuenta/`)}
      >
        <Text style={styles.botonTexto}>Solicitar eliminación de cuenta</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 16, gap: 12 },
  tarjeta: { borderRadius: 14, padding: 12, gap: 12 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12, backgroundColor: "#fff" },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  error: { color: colores.peligro, textAlign: "center" },
  exito: { color: colores.accent, textAlign: "center" },
});
