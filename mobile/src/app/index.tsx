import { LinearGradient } from 'expo-linear-gradient';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import Animated, { FadeIn, FadeInDown, LinearTransition } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { API_URL } from '@/api/config';
import { BadgeDemo } from '@/components/BadgeDemo';
import { MapaCasa } from '@/components/MapaCasa';
import { useEsEscritorio } from '@/lib/responsive';
import { generarCorrida } from '@/mock/demo';
import { useCorridaCtx } from '@/state/CorridaProvider';
import { c, pesos, r, s } from '@/theme';
import {
  AMBIENTES,
  DEFAULTS_POR_TIPO,
  LIMITES,
  LIMITES_AMBIENTE,
  type Espacio,
  type TipoAmbiente,
} from '@/types';

function etiquetaAmbiente(tipo: TipoAmbiente): string {
  return AMBIENTES.find((a) => a.id === tipo)?.nombre ?? tipo;
}

type FuenteElegida = 'vivo-det' | 'vivo-agentico' | 'demo';

/** Health-check del backend: si no responde, no tiene sentido ofrecer los
 *  modos en vivo — mejor caer directo al modo Demo sin que el usuario choque
 *  con un error de red a medio flujo. */
function useSaludBackend() {
  const [disponible, setDisponible] = useState<boolean | null>(null);
  useEffect(() => {
    let vivo = true;
    fetch(`${API_URL}/salud`)
      .then((r) => r.ok)
      .catch(() => false)
      .then((ok) => vivo && setDisponible(ok));
    return () => {
      vivo = false;
    };
  }, []);
  return disponible;
}

export default function Inicio() {
  const insets = useSafeAreaInsets();
  const escritorio = useEsEscritorio();
  const { correr, correrVivo } = useCorridaCtx();
  const backendVivo = useSaludBackend();

  // Determinista por defecto: sin LLM, sin red, instantáneo. El agéntico gasta
  // ~35 requests contra 20/día/modelo, así que queda detrás de una elección
  // explícita. Si el backend no responde, se cae al modo Demo (traza congelada).
  const [fuente, setFuente] = useState<FuenteElegida>('vivo-det');

  useEffect(() => {
    if (backendVivo === false) setFuente('demo');
  }, [backendVivo]);

  const [tipo, setTipo] = useState<TipoAmbiente>('bano');
  const [largo, setLargo] = useState('2');
  const [ancho, setAncho] = useState('2');
  const [altura, setAltura] = useState('2.4');
  const [presupuesto, setPresupuesto] = useState('2000000');

  // Campos condicionales por ambiente — espejan `Espacio.variables()` de
  // dominio/schemas.py: no significan nada fuera de su ambiente, así que no
  // se muestran (y no se envían) para los demás.
  const defaults = DEFAULTS_POR_TIPO[tipo];
  const [alturaEnchape, setAlturaEnchape] = useState(String(defaults.altura_enchape_m ?? 2.0));
  const [incluyeDucha, setIncluyeDucha] = useState(defaults.incluye_ducha ?? true);
  const [metrosLineales, setMetrosLineales] = useState(String(defaults.metros_lineales ?? 3.0));

  // Al cambiar de ambiente, los campos condicionales vuelven a su default
  // real (no se arrastra, por ejemplo, la altura de enchape de baño a cocina).
  useEffect(() => {
    const d = DEFAULTS_POR_TIPO[tipo];
    if (d.altura_enchape_m !== undefined) setAlturaEnchape(String(d.altura_enchape_m));
    if (d.incluye_ducha !== undefined) setIncluyeDucha(d.incluye_ducha);
    if (d.metros_lineales !== undefined) setMetrosLineales(String(d.metros_lineales));
  }, [tipo]);

  const nLargo = Number(largo) || 0;
  const nAncho = Number(ancho) || 0;
  const nAltura = Number(altura) || 0;
  const nAlturaEnchape = Number(alturaEnchape) || 0;
  const nMetrosLineales = Number(metrosLineales) || 0;
  const tope = Number(presupuesto) || 0;
  const area = nLargo * nAncho;

  const limitesA = LIMITES_AMBIENTE[tipo];
  const tieneEnchape = tipo === 'bano' || tipo === 'cocina';
  const tieneDucha = tipo === 'bano';
  const tieneMetrosLineales = tipo === 'cocina' || tipo === 'habitacion';
  const etiquetaMl = tipo === 'cocina' ? 'Mesón de cocina (ml)' : 'Clóset corrido (ml)';

  // Los rangos son los del guardrail real: `LIMITES` genérico de
  // dominio/schemas.py (Field(...)) MÁS `LIMITES_AMBIENTE` (área/lado/
  // presupuesto por tipo, de `dominio.schemas.LIMITES`). Validar solo el
  // genérico deja pasar, por ejemplo, un baño de 6x6 (dentro de lado_m) que
  // el backend rechaza igual por área_max=25.
  const ladoOk = (v: number) => v > LIMITES.lado_m.min && v < LIMITES.lado_m.max && v <= limitesA.lado_max;
  const enchapeOk = !tieneEnchape || (nAlturaEnchape > 0 && nAlturaEnchape <= nAltura);
  const valido =
    ladoOk(nLargo) &&
    ladoOk(nAncho) &&
    nAltura > LIMITES.altura_m.min &&
    nAltura < LIMITES.altura_m.max &&
    area <= limitesA.area_max &&
    tope >= limitesA.presupuesto_min &&
    enchapeOk;

  const motivo = !ladoOk(nLargo)
    ? `El largo debe estar entre ${LIMITES.lado_m.min} y ${limitesA.lado_max} m`
    : !ladoOk(nAncho)
      ? `El ancho debe estar entre ${LIMITES.lado_m.min} y ${limitesA.lado_max} m`
      : nAltura <= LIMITES.altura_m.min || nAltura >= LIMITES.altura_m.max
        ? `La altura debe estar entre ${LIMITES.altura_m.min} y ${LIMITES.altura_m.max} m`
        : area > limitesA.area_max
          ? `Un(a) ${etiquetaAmbiente(tipo)} no suele superar los ${limitesA.area_max} m²`
          : tieneEnchape && !enchapeOk
            ? 'La altura de enchape no puede superar la altura del espacio'
            : tope < limitesA.presupuesto_min
              ? `El presupuesto mínimo realista para ${etiquetaAmbiente(tipo)} es ${pesos(limitesA.presupuesto_min)}`
              : '';

  const arrancar = () => {
    const espacio: Espacio = {
      tipo,
      largo_m: nLargo,
      ancho_m: nAncho,
      altura_m: nAltura,
      altura_enchape_m: tieneEnchape ? nAlturaEnchape : null,
      incluye_ducha: tieneDucha ? incluyeDucha : null,
      puertas: 1,
      metros_lineales: tieneMetrosLineales ? nMetrosLineales : null,
      presupuesto_cop: tope,
    };
    router.push('/obra');
    if (fuente === 'demo') {
      correr(espacio, generarCorrida(espacio, 1));
    } else {
      correrVivo(espacio, fuente === 'vivo-det');
    }
  };

  const hero = (
    <Animated.View entering={FadeIn.duration(600)}>
      <Text style={e.kicker}>AGENTSPRINT · EAFIT · RESHAPEX</Text>
      <Text style={[e.titulo, escritorio && e.tituloEscritorio]}>
        No es un buscador{'\n'}de productos.
      </Text>
      <Text style={[e.sub, escritorio && e.subEscritorio]}>
        Es un cuantificador de obra que te dice que no cuando no alcanza el presupuesto.
      </Text>
      <Pressable onPress={() => router.push('/catalogo')} hitSlop={8}>
        <Text style={e.linkCatalogo}>Ver el catálogo real (2.885 productos) →</Text>
      </Pressable>
    </Animated.View>
  );

  const formulario = (
    <View style={{ gap: s.md, width: '100%' }}>
      <Animated.View entering={FadeInDown.springify()} style={e.tarjeta}>
        <Text style={e.etiqueta}>
          MODO {backendVivo === false && '· BACKEND NO DISPONIBLE, SOLO DEMO'}
        </Text>
        <View style={e.filaModos}>
          <ChipModo
            activo={fuente === 'vivo-det'}
            disabled={backendVivo === false}
            texto="Determinista"
            onPress={() => setFuente('vivo-det')}
          />
          <ChipModo
            activo={fuente === 'vivo-agentico'}
            disabled={backendVivo === false}
            texto="Agéntico"
            onPress={() => setFuente('vivo-agentico')}
          />
          <ChipModo activo={fuente === 'demo'} texto="Demo" onPress={() => setFuente('demo')} />
        </View>
        {fuente === 'vivo-agentico' && (
          <Text style={e.avisoAgentico}>
            ⚠ Corre los 3 loops LLM reales: gasta cuota del modelo. Úsalo con moderación.
          </Text>
        )}
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(100).springify()} style={e.tarjeta}>
        <Text style={e.etiqueta}>AMBIENTE</Text>
        <View style={{ marginTop: s.sm }}>
          <MapaCasa seleccion={tipo} onSeleccionar={setTipo} />
        </View>
      </Animated.View>

      {(tieneEnchape || tieneDucha || tieneMetrosLineales) && (
        <Animated.View
          entering={FadeInDown.delay(130).springify()}
          layout={LinearTransition.springify()}
          style={e.tarjeta}
        >
          <Text style={e.etiqueta}>OPCIONES DE {etiquetaAmbiente(tipo).toUpperCase()}</Text>
          <View style={{ marginTop: s.sm, gap: s.md }}>
            {tieneEnchape && (
              <View style={e.filaOpcion}>
                <Text style={e.opcionTexto}>Altura de enchape (m)</Text>
                <TextInput
                  value={alturaEnchape}
                  onChangeText={(t) => setAlturaEnchape(t.replace(/[^\d.,]/g, '').replace(',', '.'))}
                  keyboardType="decimal-pad"
                  style={e.inputOpcion}
                  maxLength={4}
                />
              </View>
            )}
            {tieneDucha && (
              <View style={e.filaOpcion}>
                <Text style={e.opcionTexto}>Tiene ducha</Text>
                <Switch
                  value={incluyeDucha}
                  onValueChange={setIncluyeDucha}
                  trackColor={{ false: c.borde, true: c.seleccion }}
                  thumbColor={c.texto}
                />
              </View>
            )}
            {tieneMetrosLineales && (
              <View style={e.filaOpcion}>
                <Text style={e.opcionTexto}>{etiquetaMl}</Text>
                <TextInput
                  value={metrosLineales}
                  onChangeText={(t) => setMetrosLineales(t.replace(/[^\d.,]/g, '').replace(',', '.'))}
                  keyboardType="decimal-pad"
                  style={e.inputOpcion}
                  maxLength={4}
                />
              </View>
            )}
          </View>
        </Animated.View>
      )}

      <Animated.View
        entering={FadeInDown.delay(160).springify()}
        layout={LinearTransition.springify()}
        style={e.tarjeta}
      >
        <Text style={e.etiqueta}>MEDIDAS</Text>
        <View style={e.filaMedidas}>
          <Medida valor={largo} set={setLargo} sufijo="largo" />
          <Text style={e.equis}>×</Text>
          <Medida valor={ancho} set={setAncho} sufijo="ancho" />
          <Text style={e.equis}>×</Text>
          <Medida valor={altura} set={setAltura} sufijo="altura" />
        </View>
        <Text style={[e.area, { textAlign: 'center' }]}>
          {area ? `${area.toFixed(2)} m² de piso` : 'Ingresa las medidas'}
        </Text>
      </Animated.View>

      <Animated.View entering={FadeInDown.delay(220).springify()} style={e.tarjeta}>
        <Text style={e.etiqueta}>TOPE</Text>
        <TextInput
          value={presupuesto}
          onChangeText={(t) => setPresupuesto(t.replace(/\D/g, ''))}
          keyboardType="number-pad"
          style={[e.inputPlata, { textAlign: 'center' }]}
          placeholder="2000000"
          placeholderTextColor={c.textoTenue}
        />
        <Text style={[e.area, { textAlign: 'center' }]}>
          {tope ? pesos(tope) : 'En pesos colombianos'}
        </Text>
      </Animated.View>

      <Pressable
        onPress={arrancar}
        disabled={!valido}
        style={({ pressed }) => [e.cta, !valido && e.ctaOff, pressed && { opacity: 0.85 }]}
      >
        <Text style={[e.ctaTexto, !valido && { color: c.textoTenue }]}>Cuantificar la obra</Text>
      </Pressable>

      {!!motivo && <Text style={e.validacion}>{motivo}</Text>}
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <LinearGradient colors={['#1A0E08', c.bg]} style={StyleSheet.absoluteFill} />

      <ScrollView
        contentContainerStyle={[
          e.cuerpo,
          escritorio && e.cuerpoEscritorio,
          escritorio && { flexGrow: 1 },
          { paddingTop: insets.top + s.lg, paddingBottom: s.xxl },
        ]}
        keyboardShouldPersistTaps="handled"
      >
        <BadgeDemo visible={fuente === 'demo'} />

        {escritorio ? (
          <View style={e.centroEscritorio}>
            <View style={e.filaEscritorio}>
              <View style={e.colHero}>{hero}</View>
              <View style={e.colFormulario}>{formulario}</View>
            </View>
          </View>
        ) : (
          <>
            {hero}
            {formulario}
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function ChipModo({
  activo,
  texto,
  onPress,
  disabled,
}: {
  activo: boolean;
  texto: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      style={[e.chip, activo && e.chipActivo, disabled && e.chipOff]}
    >
      <Text style={[e.chipTexto, activo && e.chipTextoActivo]}>{texto}</Text>
    </Pressable>
  );
}

function Medida({
  valor,
  set,
  sufijo,
}: {
  valor: string;
  set: (v: string) => void;
  sufijo: string;
}) {
  return (
    <View style={e.medida}>
      <TextInput
        value={valor}
        onChangeText={(t) => set(t.replace(/[^\d.,]/g, '').replace(',', '.'))}
        keyboardType="decimal-pad"
        style={e.inputMedida}
        maxLength={5}
      />
      <Text style={e.sufijo}>{sufijo}</Text>
    </View>
  );
}

const e = StyleSheet.create({
  cuerpo: { paddingHorizontal: s.lg, gap: s.md },
  cuerpoEscritorio: { maxWidth: 1180, alignSelf: 'center', width: '100%', paddingHorizontal: s.xl },

  centroEscritorio: { flex: 1, justifyContent: 'center' },
  filaEscritorio: {
    flexDirection: 'row',
    gap: s.xxl,
    alignItems: 'center',
    justifyContent: 'center',
  },
  colHero: { width: 460 },
  colFormulario: { width: 460 },

  kicker: { color: c.acento, fontSize: 11, fontWeight: '900', letterSpacing: 1.4 },
  titulo: { color: c.texto, fontSize: 31, fontWeight: '900', lineHeight: 36, marginTop: s.sm },
  tituloEscritorio: { fontSize: 46, lineHeight: 52 },
  sub: { color: c.textoSuave, fontSize: 14, lineHeight: 21, marginTop: s.sm },
  subEscritorio: { fontSize: 17, lineHeight: 25, maxWidth: 420 },
  linkCatalogo: { color: c.acento, fontSize: 12, fontWeight: '700', marginTop: s.md },

  tarjeta: {
    padding: s.md,
    borderRadius: r.lg,
    backgroundColor: c.surface,
    borderWidth: 1,
    borderColor: c.borde,
  },
  etiqueta: {
    color: c.textoTenue,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.2,
    textAlign: 'center',
    marginBottom: 2,
  },

  filaModos: { flexDirection: 'row', gap: s.sm, marginTop: s.sm },
  chip: {
    flex: 1,
    paddingVertical: 9,
    borderRadius: r.md,
    borderWidth: 1,
    borderColor: c.borde,
    backgroundColor: c.surfaceAlto,
    alignItems: 'center',
  },
  chipActivo: { borderColor: c.acento, backgroundColor: 'rgba(255,90,31,0.12)' },
  chipOff: { opacity: 0.4 },
  chipTexto: { color: c.textoSuave, fontSize: 12, fontWeight: '700' },
  chipTextoActivo: { color: c.acento },
  avisoAgentico: { color: c.alerta, fontSize: 11, marginTop: s.sm, lineHeight: 15 },

  filaOpcion: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  opcionTexto: { color: c.textoSuave, fontSize: 13, fontWeight: '600' },
  inputOpcion: {
    color: c.texto,
    fontSize: 16,
    fontWeight: '800',
    minWidth: 56,
    textAlign: 'right',
    fontVariant: ['tabular-nums'],
  },

  filaMedidas: { flexDirection: 'row', alignItems: 'center', marginTop: s.sm, gap: s.sm },
  medida: { flex: 1, alignItems: 'center' },
  inputMedida: {
    color: c.texto,
    fontSize: 28,
    fontWeight: '800',
    textAlign: 'center',
    width: '100%',
    paddingVertical: 2,
    fontVariant: ['tabular-nums'],
  },
  sufijo: { color: c.textoTenue, fontSize: 10, fontWeight: '700' },
  equis: { color: c.textoTenue, fontSize: 18, marginBottom: 14 },
  area: { color: c.textoSuave, fontSize: 12, marginTop: s.sm, fontWeight: '600' },

  inputPlata: {
    color: c.texto,
    fontSize: 29,
    fontWeight: '800',
    marginTop: s.xs,
    fontVariant: ['tabular-nums'],
  },

  cta: {
    marginTop: s.sm,
    paddingVertical: 17,
    borderRadius: r.lg,
    backgroundColor: c.acento,
    alignItems: 'center',
  },
  ctaOff: { backgroundColor: c.surfaceAlto },
  ctaTexto: { color: '#100804', fontSize: 16, fontWeight: '900' },
  validacion: { color: c.alerta, fontSize: 12, textAlign: 'center', lineHeight: 17 },
});
