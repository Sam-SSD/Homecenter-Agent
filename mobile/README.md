# Obra · front del cotizador Homecenter

Frontend web + móvil (un solo código, Expo Router + `react-native-web`) para el
agente cotizador de remodelación de
[Homecenter-Agent](https://github.com/Sam-SSD/Homecenter-Agent). Cubre los
cuatro ambientes del backend — baño, cocina, habitación y sala — con la traza
del loop de agentes en vivo, un mapa de casa para elegir qué remodelar, la
lista de productos reales con foto y precio, la negociación de presupuesto, y
un chat para preguntarle al agente sobre la cotización.

**Web es la plataforma principal** (pantalla completa, layout de 2 columnas en
escritorio); Android corre exactamente el mismo código.

---

## Correr esto ahora mismo

### 1. Requisitos
- Node 20 LTS o más nuevo ([nodejs.org](https://nodejs.org))
- npm (viene con Node)
- Para Android: [Expo Go](https://expo.dev/go) en tu celular, **o** Android
  Studio con un emulador si prefieres correrlo en tu computador

### 2. Instalar dependencias
```bash
cd mobile
npm install
```

### 3. Verla en el navegador (recomendado, es la plataforma principal)
```bash
npm run web
```
Se abre sola en `http://localhost:8081`. Si no se abre sola, copia esa URL de
la terminal y pégala en el navegador. Recarga con `r` en la terminal si haces
un cambio y no se refleja solo.

### 4. Verla en el celular (opcional)
```bash
npm start
```
Escanea el código QR que aparece en la terminal con la app **Expo Go**
(Android o iOS). El celular y el computador deben estar en la misma red WiFi.

Para un build nativo real en Android (sin Expo Go):
```bash
npm run android   # requiere un emulador corriendo o un celular por USB con depuración activada
```

### 5. Qué vas a ver, en orden
1. **Inicio** (`/`): elige el ambiente tocando el mapa de casa (baño, cocina,
   habitación o sala), ajusta medidas y las opciones que aparecen según el
   ambiente (ducha, altura de enchape, metros lineales), define el
   presupuesto y toca **"Cuantificar la obra"**.
2. **Traza en vivo** (`/obra`): el loop de agentes (Supervisor, Cuantificador,
   Comprador, Negociador, Verificador) corre paso a paso con su vocabulario
   real. Al terminar, un botón lleva a los productos.
3. **Cotización** (`/cotizacion`): primero los productos reales (con foto —
   tócala para ver precio grande sin salir de la app), después la
   negociación — ahí decides si apruebas los recortes o subes el presupuesto.
4. **Catálogo** (`/catalogo`, link desde Inicio): explora los 2.885 productos
   reales del snapshot, con foto, precio y buscador.
5. **Preguntas** (`/qa`, link desde Cotización): un chat para preguntarle al
   agente sobre la cotización que acabas de generar.

Si algo no arranca: borra `node_modules` y `.expo`, y vuelve a `npm install`.
Si el puerto 8081 está ocupado, Expo te ofrece otro automáticamente — solo
di que sí.

---

## Qué es y qué no es

**No habla con el agente real todavía.** El backend
([Homecenter-Agent](https://github.com/Sam-SSD/Homecenter-Agent)) expone
Streamlit, no HTTP, así que no hay endpoint al cual conectarse. Esta app
reproduce trazas con las mismas fórmulas y el mismo vocabulario del backend, y
lo dice en pantalla con un badge de **MODO DEMO** que no se puede ocultar.

Eso es deliberado: presentar una traza reproducida como si fuera salida del
agente sería vender trabajo de LLM que nunca ocurrió. El badge se quita el día
que exista un endpoint real, no antes.

Lo que sí es: una demo instalable (web o APK) con la traza del loop como
espectáculo — carriles por actor, tarjeta roja cuando el Verificador rechaza,
tachado del Cuantificador cuando hay `memoria_hit`, aprobación humana por
gesto, y ahora también foto real de cada producto y un chat de preguntas.

## Para conectarlo en vivo (no está hecho, no toca este repo)

Hacen falta dos cosas, y solo la segunda vive acá:

1. **En el backend**: un `api.py` que cuelgue de `Traza(on_paso=...)`
   ([dominio/traza.py:8](https://github.com/Sam-SSD/Homecenter-Agent)) y publique
   los pasos como SSE, más un endpoint que envuelva `agentes/qa.py::responder`
   para el chat. El gancho de traza ya existe y ya está bajo test en
   `prove.py`; `app.py:132` lo usa para pintar Streamlit en vivo.
2. **Acá**: reemplazar `reproducirCache` en [src/api/stream.ts](src/api/stream.ts)
   por un lector de `response.body`, y el mock de
   [src/api/qa.ts](src/api/qa.ts) por un `fetch` real. Importante para la
   traza: con **`expo/fetch`**, no el fetch global — el de React Native no
   expone el stream, así que la traza llegaría toda junta al final.

## El contrato

[src/types.ts](src/types.ts) espeja `dominio/schemas.py` campo por campo, sin
traducir nombres (si allá dice `total_cop`, acá dice `total_cop`), más
`LIMITES_AMBIENTE`/`DEFAULTS_POR_TIPO` que espejan los límites y defaults por
ambiente del guardrail real (`dominio.schemas.LIMITES`).

Los `tipo` de paso salieron de grepear `.paso(` en el repo del backend
(`agentes/loop.py`, `agentes/llm.py`, `agentes/supervisor.py`,
`agentes/subagentes.py`), no de la imaginación:

| actor · tipo | Qué es en el pitch |
|---|---|
| `verificador/rechazo` | auto-corrección — la tarjeta roja que se sacude |
| `supervisor/memoria_hit` | prueba de memoria — el Cuantificador sale tachado |
| `comprador/sku_inventado` | el LLM alucinó un SKU y fue atrapado |
| `llm/fallback`, `llm/espera` | rotación de llaves Gemini ante 429 |
| `cuantificador/divergencia` | el LLM no coincidió con el número de Python |
| `llm/llm`, `*/error_tool`, `*/limite` | consulta al modelo, error de herramienta, tope de iteraciones |

### Diferencia que importa

El backend modela `recortes` como `list[str]` y la aprobación humana como un
solo `aprobada_por_humano: bool` sobre toda la cotización. Por eso la
compuerta es una sola y no una por recorte, y por eso vive en
`/cotizacion` **después** de la lista de productos: el usuario ve qué está
comprando antes de que se le pida decidir. Si alguien enriquece `recortes` a
objetos con `ahorro` e `impacto`, el swipe se puede volver por-recorte.

## Correr en producción / repartir

### APK Android
```bash
cd android && ./gradlew assembleRelease
# android/app/build/outputs/apk/release/app-release.apk
```
Firmada con la keystore de debug: instalable de inmediato, sin Play Store y sin
cuenta de Expo. Solo trae `arm64-v8a` — las otras tres ABIs eran ~57 MB de
emulador y teléfonos de 32 bits. Para probar en emulador:
`./gradlew assembleRelease -PreactNativeArchitectures=x86_64`.

Para repartirla: `python -m http.server 8080` sobre la carpeta del APK y un QR
apuntando a `http://<tu-ip>:8080/app-release.apk`.

### Build web estático
```bash
npx expo export --platform web
# carpeta dist/, servible con cualquier servidor estático
```

## Mapa del código

| Archivo | Qué es |
|---|---|
| `src/app/index.tsx` | mapa de casa, medidas, tope, opciones por ambiente, validación igual a la de Pydantic |
| `src/app/obra.tsx` | la traza en vivo del loop de agentes, resumen al terminar |
| `src/app/cotizacion.tsx` | productos con foto y fuente, negociación (aprobar/rechazar), fases, botón del turno 2 |
| `src/app/catalogo.tsx` | grilla del catálogo real con foto, buscador y categorías |
| `src/app/qa.tsx` | chat de preguntas sobre la cotización generada |
| `src/components/MapaCasa.tsx` | selector visual de ambiente (plano de casa) |
| `src/components/ProductoPreview.tsx` | miniatura + modal de foto/precio de un producto |
| `src/components/PasoCard.tsx` | un paso de traza, con carril y énfasis por tipo |
| `src/components/AgentLanes.tsx` | la tira que tacha al Cuantificador, distingue actores deterministas |
| `src/components/AprobacionHumana.tsx` | la compuerta humana, por gesto |
| `src/components/MensajeQA.tsx` | una burbuja del chat de preguntas |
| `src/components/BadgeDemo.tsx` | el badge que impide presentar esto como el agente |
| `src/state/corrida.ts` | reduce `PasoTraza[]` a estado de UI |
| `src/state/qa.ts` | historial del chat de preguntas |
| `src/lib/responsive.ts` | punto único de corte web/escritorio (`useEsEscritorio`) |
| `src/mock/demo.ts` | generador paramétrico de trazas. **No es el agente.** |
| `src/api/qa.ts` | mock del contrato real de `agentes/qa.py::responder` |

## Pendiente

Los iconos de `assets/images/` son placeholders prestados de otro proyecto. Es
lo primero que ve el jurado al instalar la APK.
