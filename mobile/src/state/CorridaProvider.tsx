import { createContext, useContext, type ReactNode } from 'react';

import { useCorrida } from './corrida';

type Ctx = ReturnType<typeof useCorrida>;

const CorridaCtx = createContext<Ctx | null>(null);

/**
 * Una sola corrida viva para toda la app: la traza y la cotización son dos
 * pantallas del mismo evento, no dos fetch distintos.
 */
export function CorridaProvider({ children }: { children: ReactNode }) {
  const valor = useCorrida();
  return <CorridaCtx.Provider value={valor}>{children}</CorridaCtx.Provider>;
}

export function useCorridaCtx(): Ctx {
  const v = useContext(CorridaCtx);
  if (!v) throw new Error('useCorridaCtx fuera de <CorridaProvider>');
  return v;
}
