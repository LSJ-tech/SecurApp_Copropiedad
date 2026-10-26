// Inicializa Sentry apenas se importa este módulo (no en un useEffect --
// tiene que capturar errores desde el arranque mismo de la app, antes de
// que monte el primer componente). Se importa primero que nada en
// app/_layout.tsx.
//
// EXPO_PUBLIC_SENTRY_DSN vacío (todavía sin cuenta de Sentry, o en
// desarrollo local) deja Sentry sin inicializar -- no es secreto (un DSN
// es de solo-ingesta, pensado para ir embebido en el cliente, por eso
// EXPO_PUBLIC_* y commiteado en .env igual que EXPO_PUBLIC_API_URL).
import * as Sentry from "@sentry/react-native";

const dsn = process.env.EXPO_PUBLIC_SENTRY_DSN;

if (dsn) {
  Sentry.init({ dsn });
}
