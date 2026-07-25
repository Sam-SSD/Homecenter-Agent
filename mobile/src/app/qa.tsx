import { router } from 'expo-router';
import { useRef, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';

import { BadgeDemo } from '@/components/BadgeDemo';
import { MensajeQA } from '@/components/MensajeQA';
import { useEsEscritorio } from '@/lib/responsive';
import { useCorridaCtx } from '@/state/CorridaProvider';
import { useQA } from '@/state/qa';
import { c, pesos, r, s } from '@/theme';
import { AMBIENTES } from '@/types';

const SUGERIDAS = ['¿Cuál es el total?', '¿Qué se recortó?', '¿Cuánto cuesta el enchape?'];

export default function QAPantalla() {
  const { estado } = useCorridaCtx();
  const escritorio = useEsEscritorio();
  const { mensajes, enviando, error, enviar } = useQA(estado.cotizacion, estado.fuente);
  const [texto, setTexto] = useState('');
  const scroll = useRef<ScrollView>(null);

  if (!estado.cotizacion) {
    return (
      <View style={e.vacioPantalla}>
        <Text style={e.vacioTitulo}>Todavía no hay una cotización</Text>
        <Text style={e.vacioTexto}>
          Genera una cotización primero para poder preguntarle al agente sobre ella.
        </Text>
        <Pressable style={e.ctaVolver} onPress={() => router.push('/')}>
          <Text style={e.ctaVolverTexto}>Ir al inicio</Text>
        </Pressable>
      </View>
    );
  }

  const cot = estado.cotizacion;
  const nombreAmbiente = AMBIENTES.find((a) => a.id === cot.espacio.tipo)?.nombre ?? cot.espacio.tipo;

  const enviarTexto = async (p: string) => {
    if (!p.trim() || enviando) return;
    setTexto('');
    await enviar(p);
    requestAnimationFrame(() => scroll.current?.scrollToEnd({ animated: true }));
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <View style={e.encabezado}>
        <BadgeDemo visible={estado.fuente === 'cache'} />
        <View style={e.contexto}>
          <View style={{ flex: 1 }}>
            <Text style={e.contextoTitulo}>Cotización de {nombreAmbiente}</Text>
            <Text style={e.contextoSub}>
              Total {pesos(cot.total_cop)} · {cot.items.length} productos
            </Text>
          </View>
        </View>
      </View>

      <ScrollView
        ref={scroll}
        contentContainerStyle={[
          e.cuerpo,
          escritorio && e.cuerpoEscritorio,
          mensajes.length === 0 && e.cuerpoVacio,
        ]}
        onContentSizeChange={() => scroll.current?.scrollToEnd({ animated: true })}
      >
        {mensajes.length === 0 && (
          <Animated.View entering={FadeIn.delay(150)} style={e.vacioChat}>
            <Text style={e.vacioChatTexto}>Pregúntale al agente sobre esta cotización</Text>
            <View style={e.sugeridas}>
              {SUGERIDAS.map((sug) => (
                <Pressable key={sug} style={e.sugerida} onPress={() => enviarTexto(sug)}>
                  <Text style={e.sugeridaTexto}>{sug}</Text>
                </Pressable>
              ))}
            </View>
          </Animated.View>
        )}
        {mensajes.map((m) => (
          <MensajeQA key={m.id} mensaje={m} />
        ))}
        {enviando && <Text style={e.escribiendo}>El agente está consultando…</Text>}
        {error && <Text style={e.error}>{error}</Text>}
      </ScrollView>

      <View style={e.pieFondo}>
        <View style={[e.pie, escritorio && e.pieEscritorio]}>
          <TextInput
            value={texto}
            onChangeText={setTexto}
            placeholder="Ej: ¿por qué se recortó el enchape?"
            placeholderTextColor={c.textoTenue}
            style={e.input}
            onSubmitEditing={() => enviarTexto(texto)}
            returnKeyType="send"
          />
          <Pressable
            onPress={() => enviarTexto(texto)}
            disabled={!texto.trim() || enviando}
            style={[e.enviar, (!texto.trim() || enviando) && e.enviarOff]}
          >
            <Text style={e.enviarTexto}>Enviar</Text>
          </Pressable>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const e = StyleSheet.create({
  encabezado: { paddingHorizontal: s.md, paddingTop: s.sm, gap: s.sm, borderBottomWidth: 1, borderColor: c.borde, paddingBottom: s.sm },
  contexto: { flexDirection: 'row', alignItems: 'center', gap: s.sm },
  contextoTitulo: { color: c.texto, fontSize: 14, fontWeight: '800' },
  contextoSub: { color: c.textoTenue, fontSize: 11, marginTop: 1 },

  cuerpo: { padding: s.md, paddingBottom: s.xl, flexGrow: 1 },
  cuerpoEscritorio: { maxWidth: 760, alignSelf: 'center', width: '100%' },
  cuerpoVacio: { justifyContent: 'center', alignItems: 'center' },

  vacioChat: { alignItems: 'center', gap: s.md, maxWidth: 420 },
  vacioChatTexto: { color: c.textoSuave, textAlign: 'center', fontSize: 14, fontWeight: '600' },
  sugeridas: { flexDirection: 'row', flexWrap: 'wrap', gap: s.sm, justifyContent: 'center' },
  sugerida: {
    paddingHorizontal: s.md,
    paddingVertical: s.sm,
    borderRadius: r.lg,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
  },
  sugeridaTexto: { color: c.textoSuave, fontSize: 12, fontWeight: '600' },

  escribiendo: { color: c.textoTenue, fontSize: 12, fontStyle: 'italic', marginTop: s.xs },
  error: { color: c.falla, fontSize: 12, marginTop: s.sm },

  pieFondo: { borderTopWidth: 1, borderColor: c.borde, backgroundColor: c.bg },
  pie: { flexDirection: 'row', gap: s.sm, padding: s.md, alignItems: 'center' },
  pieEscritorio: { maxWidth: 760, alignSelf: 'center', width: '100%' },
  input: {
    flex: 1,
    color: c.texto,
    backgroundColor: c.surface,
    borderRadius: r.xl,
    borderWidth: 1,
    borderColor: c.borde,
    paddingHorizontal: s.lg,
    paddingVertical: 12,
    fontSize: 14,
  },
  enviar: {
    paddingHorizontal: s.lg,
    height: 44,
    borderRadius: 22,
    backgroundColor: c.acento,
    alignItems: 'center',
    justifyContent: 'center',
  },
  enviarOff: { backgroundColor: c.surfaceAlto },
  enviarTexto: { color: '#100804', fontWeight: '900', fontSize: 13 },

  vacioPantalla: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: s.xl, gap: s.sm },
  vacioTitulo: { color: c.texto, fontSize: 17, fontWeight: '800', textAlign: 'center' },
  vacioTexto: { color: c.textoSuave, fontSize: 13, textAlign: 'center', lineHeight: 19 },
  ctaVolver: {
    marginTop: s.md,
    paddingHorizontal: s.lg,
    paddingVertical: s.sm,
    borderRadius: r.md,
    backgroundColor: c.acento,
  },
  ctaVolverTexto: { color: '#100804', fontWeight: '800', fontSize: 13 },
});
