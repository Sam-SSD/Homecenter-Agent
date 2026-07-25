import { FlashList } from '@shopify/flash-list';
import { useMemo, useState } from 'react';
import { Image, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';

import { BadgeDemo } from '@/components/BadgeDemo';
import { VistaPreviaModal } from '@/components/ProductoPreview';
import { CATEGORIAS_CON_PRODUCTOS, buscarTexto, nombreCategoria, productosDeCategoria } from '@/data/catalogo';
import { useEsEscritorio } from '@/lib/responsive';
import { c, pesos, r, s } from '@/theme';
import type { Producto } from '@/types';

/**
 * Explorador del catálogo real: 2885 productos parseados de páginas cacheadas
 * de Homecenter (ver `scripts/parse_catalogo.py`). Sin red, sin backend — solo
 * el JSON bundleado. Tocar una tarjeta abre una previsualización con foto y
 * precio antes de decidir si vale la pena salir a la página real.
 */
export default function Catalogo() {
  const escritorio = useEsEscritorio();
  const [consulta, setConsulta] = useState('');
  const [categoria, setCategoria] = useState<string | null>(null);
  const [previa, setPrevia] = useState<Producto | null>(null);

  const resultados = useMemo<Producto[]>(() => {
    if (consulta.trim().length >= 2) return buscarTexto(consulta, 100);
    if (categoria) return productosDeCategoria(categoria);
    return [];
  }, [consulta, categoria]);

  const columnas = escritorio ? 3 : 1;

  return (
    <View style={{ flex: 1 }}>
      <View style={[e.encabezado, escritorio && e.centrado]}>
        <BadgeDemo />
        <Text style={e.contador}>2.885 productos reales · sin red</Text>
      </View>

      <View style={[e.buscador, escritorio && e.centrado]}>
        <TextInput
          value={consulta}
          onChangeText={(t) => {
            setConsulta(t);
            if (t.trim().length >= 2) setCategoria(null);
          }}
          placeholder="Buscar: sanitario blanco, sofá 3 puestos…"
          placeholderTextColor={c.textoTenue}
          style={e.input}
          autoCapitalize="none"
        />
      </View>

      {!consulta && (
        <View style={escritorio && e.centrado}>
          <FlashList
            horizontal
            showsHorizontalScrollIndicator={false}
            data={CATEGORIAS_CON_PRODUCTOS}
            keyExtractor={(item) => item}
            contentContainerStyle={{ paddingHorizontal: s.md, paddingBottom: s.sm }}
            renderItem={({ item }) => (
              <Pressable
                onPress={() => setCategoria(item === categoria ? null : item)}
                style={[e.chip, categoria === item && e.chipOn]}
              >
                <Text style={[e.chipTexto, categoria === item && { color: c.acento }]}>
                  {nombreCategoria(item)}
                </Text>
              </Pressable>
            )}
          />
        </View>
      )}

      {resultados.length === 0 ? (
        <Animated.View entering={FadeIn.delay(200)} style={e.vacioBox}>
          <Text style={e.vacio}>
            {consulta || categoria
              ? 'Sin resultados'
              : 'Busca un producto o elige una categoría arriba'}
          </Text>
        </Animated.View>
      ) : (
        <FlashList
          key={columnas}
          data={resultados}
          numColumns={columnas}
          keyExtractor={(item) => item.sku}
          contentContainerStyle={[
            { padding: s.md, paddingBottom: s.xxl },
            escritorio && e.centradoLista,
          ]}
          renderItem={({ item, index }) => (
            <TarjetaProducto
              producto={item}
              idx={index}
              columnas={columnas}
              onPress={() => setPrevia(item)}
            />
          )}
        />
      )}

      {previa && <VistaPreviaModal producto={previa} visible onCerrar={() => setPrevia(null)} />}
    </View>
  );
}

function TarjetaProducto({
  producto,
  idx,
  columnas,
  onPress,
}: {
  producto: Producto;
  idx: number;
  columnas: number;
  onPress: () => void;
}) {
  return (
    <Animated.View
      entering={FadeInDown.delay(Math.min(idx, 12) * 30).springify()}
      style={[e.tarjetaEnvoltura, columnas > 1 && { flex: 1 / columnas }]}
    >
      <Pressable onPress={onPress} style={({ pressed }) => [e.tarjeta, pressed && { opacity: 0.75 }]}>
        <View style={e.foto}>
          {producto.imagen_url ? (
            <Image source={{ uri: producto.imagen_url }} style={e.imagen} resizeMode="cover" />
          ) : (
            <Text style={e.sinFoto}>Sin foto</Text>
          )}
        </View>
        <View style={e.info}>
          <Text style={e.nombre} numberOfLines={2}>
            {producto.nombre}
          </Text>
          <Text style={e.meta}>
            SKU {producto.sku} · {nombreCategoria(producto.categoria)}
          </Text>
          <Text style={e.precio}>{pesos(producto.precio)}</Text>
        </View>
      </Pressable>
    </Animated.View>
  );
}

const e = StyleSheet.create({
  centrado: { maxWidth: 1180, alignSelf: 'center', width: '100%' },
  centradoLista: { maxWidth: 1180, alignSelf: 'center', width: '100%' },
  encabezado: { padding: s.md, gap: s.xs },
  contador: { color: c.textoTenue, fontSize: 11, fontWeight: '600' },

  buscador: { paddingHorizontal: s.md, paddingBottom: s.sm },
  input: {
    color: c.texto,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
    borderRadius: r.md,
    paddingHorizontal: s.md,
    paddingVertical: 12,
    fontSize: 14,
  },

  chip: {
    paddingHorizontal: s.md,
    paddingVertical: s.sm,
    borderRadius: r.sm,
    backgroundColor: c.surfaceAlto,
    borderWidth: 1,
    borderColor: 'transparent',
    marginRight: s.sm,
  },
  chipOn: { borderColor: c.acento, backgroundColor: 'rgba(255,90,31,0.12)' },
  chipTexto: { color: c.textoSuave, fontSize: 12, fontWeight: '700', textTransform: 'capitalize' },

  vacioBox: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: s.xl },
  vacio: { color: c.textoTenue, fontSize: 13, textAlign: 'center' },

  tarjetaEnvoltura: { padding: s.xs },
  tarjeta: {
    borderRadius: r.md,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
    overflow: 'hidden',
  },
  foto: {
    width: '100%',
    aspectRatio: 1,
    backgroundColor: c.surfaceAlto,
    alignItems: 'center',
    justifyContent: 'center',
  },
  imagen: { width: '100%', height: '100%' },
  sinFoto: { color: c.textoTenue, fontSize: 11 },
  info: { padding: s.sm },
  nombre: { color: c.texto, fontSize: 13, fontWeight: '600', lineHeight: 18, minHeight: 36 },
  meta: { color: c.textoTenue, fontSize: 10, marginTop: 3, textTransform: 'capitalize' },
  precio: { color: c.acento, fontSize: 14, fontWeight: '800', fontVariant: ['tabular-nums'], marginTop: 4 },
});
