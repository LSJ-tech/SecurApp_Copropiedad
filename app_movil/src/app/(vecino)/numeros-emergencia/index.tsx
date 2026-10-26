import { useEffect, useState } from "react";
import * as Linking from "expo-linking";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";

import {
  listarMisPropuestas,
  listarNumerosEmergencia,
  proponerNumero,
  NumeroEmergenciaOut,
  PropuestaOut,
} from "@/api/numerosEmergencia";
import { primerMensajeDeError } from "@/api/erroresFormulario";
import { colores } from "@/theme/colores";

export default function NumerosEmergenciaScreen() {
  const [numeros, setNumeros] = useState<NumeroEmergenciaOut[] | null>(null);
  const [misPropuestas, setMisPropuestas] = useState<PropuestaOut[]>([]);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [mostrarFormulario, setMostrarFormulario] = useState(false);
  const [categoria, setCategoria] = useState("otro");
  const [nombre, setNombre] = useState("");
  const [telefono, setTelefono] = useState("");
  const [nota, setNota] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [errorFormulario, setErrorFormulario] = useState<string | null>(null);
  const [confirmacion, setConfirmacion] = useState<string | null>(null);

  function cargar() {
    setErrorCarga(null);
    Promise.all([listarNumerosEmergencia(), listarMisPropuestas()])
      .then(([numerosRes, propuestasRes]) => {
        setNumeros(numerosRes);
        setMisPropuestas(propuestasRes);
      })
      .catch(() => setErrorCarga("No se pudo cargar los números de emergencia."));
  }

  useEffect(cargar, []);

  async function manejarLlamar(telefonoNumero: string) {
    await Linking.openURL(`tel:${telefonoNumero.replace(/\s+/g, "")}`);
  }

  async function manejarEnviarPropuesta() {
    setErrorFormulario(null);
    setEnviando(true);
    try {
      await proponerNumero({ categoria, nombre, telefono, nota: nota || undefined });
      const propuestas = await listarMisPropuestas();
      setMisPropuestas(propuestas);
      setNombre("");
      setTelefono("");
      setNota("");
      setMostrarFormulario(false);
      setConfirmacion("Gracias, tu propuesta quedó pendiente de revisión.");
    } catch (error) {
      setErrorFormulario(primerMensajeDeError(error));
    } finally {
      setEnviando(false);
    }
  }

  if (errorCarga) {
    return (
      <View style={[styles.container, styles.contenido]}>
        <Text style={styles.error}>{errorCarga}</Text>
        <Pressable style={styles.boton} onPress={cargar}>
          <Text style={styles.botonTexto}>Reintentar</Text>
        </Pressable>
      </View>
    );
  }

  if (numeros === null) return null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.contenido}>
      <Text style={styles.titulo}>Números de emergencia</Text>
      {numeros.map((numero, indice) => (
        <Pressable
          key={numero.id}
          testID={`fila-numero-${indice}`}
          style={styles.fila}
          onPress={() => manejarLlamar(numero.telefono)}
        >
          <Text style={styles.nombreNumero}>{numero.nombre}</Text>
          <Text style={styles.detalleNumero}>{numero.telefono}</Text>
        </Pressable>
      ))}

      {misPropuestas.length > 0 && (
        <>
          <Text style={styles.titulo}>Mis propuestas</Text>
          {misPropuestas.map((propuesta) => (
            <View key={propuesta.id} style={styles.fila}>
              <Text style={styles.nombreNumero}>{propuesta.nombre}</Text>
              <Text style={styles.detalleNumero}>{propuesta.estado_display}</Text>
            </View>
          ))}
        </>
      )}

      {confirmacion && <Text style={styles.exito}>{confirmacion}</Text>}

      {!mostrarFormulario ? (
        <Pressable style={styles.boton} onPress={() => setMostrarFormulario(true)}>
          <Text style={styles.botonTexto}>Proponer un número</Text>
        </Pressable>
      ) : (
        <View style={styles.formulario}>
          {errorFormulario && <Text style={styles.error}>{errorFormulario}</Text>}
          <TextInput
            style={styles.input}
            placeholder="Categoría (ej. electricidad, agua, gas, otro)"
            value={categoria}
            onChangeText={setCategoria}
          />
          <TextInput style={styles.input} placeholder="Nombre" value={nombre} onChangeText={setNombre} />
          <TextInput style={styles.input} placeholder="Teléfono" value={telefono} onChangeText={setTelefono} />
          <TextInput style={styles.input} placeholder="Nota (opcional)" value={nota} onChangeText={setNota} />
          <Pressable style={styles.boton} onPress={manejarEnviarPropuesta} disabled={enviando}>
            <Text style={styles.botonTexto}>Enviar</Text>
          </Pressable>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1 },
  contenido: { padding: 16, gap: 12 },
  titulo: { fontSize: 18, fontWeight: "700", color: colores.primary },
  // Acento (borde lateral), nunca relleno completo -- la lista de
  // números puede crecer (nacionales + los que agregue cada condominio),
  // no debe volverse muchos bloques de color repetidos (D-03).
  fila: { borderLeftWidth: 3, borderLeftColor: colores.primary, borderRadius: 4, padding: 12 },
  nombreNumero: { fontWeight: "600" },
  detalleNumero: { color: colores.secondary },
  formulario: { gap: 12 },
  input: { borderWidth: 1, borderColor: colores.slate, borderRadius: 8, padding: 12 },
  boton: { backgroundColor: colores.primary, borderRadius: 8, padding: 14, alignItems: "center" },
  botonTexto: { color: "#fff", fontWeight: "600" },
  error: { color: colores.peligro, textAlign: "center" },
  exito: { color: colores.accent, textAlign: "center" },
});
