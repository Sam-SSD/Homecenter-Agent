import * as Haptics from 'expo-haptics';
import * as WebBrowser from 'expo-web-browser';
import { useState } from 'react';
import { Image, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { c, pesos, r, s } from '@/theme';
import type { Producto } from '@/types';

/**
 * Previsualización de producto: antes solo había un link que sacaba al juez
 * de la app. Esto muestra foto + precio + SKU sin salir, y el link real queda
 * como acción explícita adentro, no como el único gesto disponible.
 */
export function MiniaturaProducto({
  producto,
  tamaño = 56,
}: {
  producto: Producto;
  tamaño?: number;
}) {
  const [abierto, setAbierto] = useState(false);

  return (
    <>
      <Pressable
        onPress={() => setAbierto(true)}
        style={[e.miniatura, { width: tamaño, height: tamaño }]}
        accessibilityLabel={`Ver foto y precio de ${producto.nombre}`}
      >
        {producto.imagen_url ? (
          <Image source={{ uri: producto.imagen_url }} style={e.imagen} resizeMode="cover" />
        ) : (
          <Text style={e.sinFoto}>Sin foto</Text>
        )}
      </Pressable>

      <VistaPreviaModal producto={producto} visible={abierto} onCerrar={() => setAbierto(false)} />
    </>
  );
}

export function VistaPreviaModal({
  producto,
  visible,
  onCerrar,
}: {
  producto: Producto;
  visible: boolean;
  onCerrar: () => void;
}) {
  const abrirEnHomecenter = async () => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await WebBrowser.openBrowserAsync(producto.url, { toolbarColor: c.bg, controlsColor: c.acento });
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onCerrar}>
      <Pressable style={e.fondo} onPress={onCerrar}>
        <Pressable style={e.tarjeta} onPress={() => {}}>
          <Pressable style={e.cerrar} onPress={onCerrar} hitSlop={10}>
            <Text style={e.cerrarTexto}>✕</Text>
          </Pressable>

          <View style={e.fotoGrande}>
            {producto.imagen_url ? (
              <Image source={{ uri: producto.imagen_url }} style={e.imagenGrande} resizeMode="contain" />
            ) : (
              <Text style={e.sinFoto}>Sin foto disponible</Text>
            )}
          </View>

          <Text style={e.nombre} numberOfLines={3}>
            {producto.nombre}
          </Text>
          <Text style={e.precio}>{pesos(producto.precio)}</Text>
          <Text style={e.meta}>
            SKU {producto.sku}
            {producto.marca ? ` · ${producto.marca}` : ''} · {producto.unidad}
          </Text>

          <Pressable style={e.ctaAbrir} onPress={abrirEnHomecenter}>
            <Text style={e.ctaAbrirTexto}>Abrir en Homecenter</Text>
          </Pressable>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const e = StyleSheet.create({
  miniatura: {
    borderRadius: r.md,
    overflow: 'hidden',
    backgroundColor: c.surfaceAlto,
    borderWidth: 1,
    borderColor: c.borde,
    alignItems: 'center',
    justifyContent: 'center',
  },
  imagen: { width: '100%', height: '100%' },
  sinFoto: { color: c.textoTenue, fontSize: 9, textAlign: 'center', padding: 4 },

  fondo: {
    flex: 1,
    backgroundColor: 'rgba(4,5,7,0.72)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: s.lg,
  },
  tarjeta: {
    width: '100%',
    maxWidth: 420,
    backgroundColor: c.surface,
    borderRadius: r.xl,
    borderWidth: 1,
    borderColor: c.borde,
    padding: s.lg,
  },
  cerrar: {
    position: 'absolute',
    top: s.sm,
    right: s.sm,
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: c.surfaceAlto,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1,
  },
  cerrarTexto: { color: c.textoSuave, fontSize: 14, fontWeight: '800' },

  fotoGrande: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: r.lg,
    backgroundColor: c.surfaceAlto,
    alignItems: 'center',
    justifyContent: 'center',
    overflow: 'hidden',
  },
  imagenGrande: { width: '100%', height: '100%' },

  nombre: { color: c.texto, fontSize: 15, fontWeight: '700', marginTop: s.md, lineHeight: 20 },
  precio: {
    color: c.acento,
    fontSize: 24,
    fontWeight: '900',
    marginTop: 4,
    fontVariant: ['tabular-nums'],
  },
  meta: { color: c.textoTenue, fontSize: 11, marginTop: 4 },

  ctaAbrir: {
    marginTop: s.md,
    paddingVertical: 13,
    borderRadius: r.md,
    backgroundColor: c.surfaceAlto,
    borderWidth: 1,
    borderColor: c.acento,
    alignItems: 'center',
  },
  ctaAbrirTexto: { color: c.acento, fontWeight: '800', fontSize: 13 },
});
