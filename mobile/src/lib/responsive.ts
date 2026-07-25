import { useWindowDimensions } from 'react-native';

/** Por debajo de esto el layout se queda apilado (comportamiento móvil actual,
 *  sin cambios); por encima se activan los layouts de escritorio (columnas,
 *  ancho máximo centrado). RN no trae media queries: esto es el único punto
 *  de la app que decide el corte, para no repetir el número por archivo. */
export const ANCHO_ESCRITORIO = 820;

export function useEsEscritorio(): boolean {
  const { width } = useWindowDimensions();
  return width >= ANCHO_ESCRITORIO;
}
