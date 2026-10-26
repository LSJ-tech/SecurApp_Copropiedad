// @expo/vector-icons carga sus fuentes de forma asíncrona vía expo-font
// (Icon.loadAsync), que en jest-expo revienta con "Module '1' is missing
// from the asset registry" -- no hay fuentes reales en el entorno de
// test. Se reemplaza por un stub sin carga de fuentes, que conserva los
// props (incluido `name`) para que los tests puedan verificar qué ícono
// se está pidiendo.
jest.mock("@expo/vector-icons", () => {
  const React = require("react");
  const { Text } = require("react-native");
  return { Ionicons: (props: Record<string, unknown>) => React.createElement(Text, props) };
});
