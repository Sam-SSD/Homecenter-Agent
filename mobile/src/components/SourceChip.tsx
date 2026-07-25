import * as Haptics from 'expo-haptics';
import * as WebBrowser from 'expo-web-browser';
import { Pressable, StyleSheet, Text } from 'react-native';

import { c, r, s } from '@/theme';

/** Concepto de UI, no del backend: allá la fuente es un `fuente_regla: str` o
 *  la `url` del producto. Acá se unifican para poder pintarlas igual. */
export interface Fuente {
  source_id: string;
  titulo: string;
  url?: string;
}

/**
 * Toda cifra lleva uno de estos. Al tocarlo abre el PDP real de Homecenter
 * dentro de la app: el juez confirma el precio en su propio celular sin salirse
 * del demo. Ese es el grounding de la rúbrica, pero como gesto en vez de párrafo.
 */
export function SourceChip({ fuente, compacto }: { fuente: Fuente; compacto?: boolean }) {
  const abrible = Boolean(fuente.url);

  const abrir = async () => {
    if (!fuente.url) return;
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await WebBrowser.openBrowserAsync(fuente.url, {
      toolbarColor: c.bg,
      controlsColor: c.acento,
      enableBarCollapsing: true,
    });
  };

  return (
    <Pressable
      onPress={abrir}
      disabled={!abrible}
      hitSlop={6}
      style={({ pressed }) => [
        e.chip,
        compacto && e.compacto,
        abrible && e.abrible,
        pressed && { opacity: 0.6 },
      ]}
    >
      <Text style={e.texto} numberOfLines={1}>
        {fuente.titulo}
      </Text>
    </Pressable>
  );
}

const e = StyleSheet.create({
  chip: {
    alignSelf: 'flex-start',
    maxWidth: '100%',
    paddingHorizontal: s.sm,
    paddingVertical: 5,
    borderRadius: r.sm,
    backgroundColor: c.surfaceAlto,
    borderWidth: 1,
    borderColor: c.borde,
  },
  compacto: { paddingVertical: 3 },
  abrible: { borderColor: 'rgba(255,90,31,0.45)' },
  texto: { color: c.textoSuave, fontSize: 11, fontWeight: '600' },
});
