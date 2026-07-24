# Cotizador de remodelación de baño — Homecenter

Sistema agéntico que cuantifica materiales de obra contra las guías técnicas
publicadas por Homecenter, busca productos reales en su catálogo, y **negocia
recortes cuando no alcanza el presupuesto** en vez de complacer al usuario.

AgentSprint by ReshapeX · Universidad EAFIT · Medellín · 25 de julio de 2026

---

## Runbook manual, paso a paso

Windows PowerShell, desde la raíz del proyecto. **Cada paso es independiente y se
puede repetir sin miedo.** En Git Bash o Linux cambia `.venv\Scripts\python` por
`.venv/bin/python`.

### Paso 0 — entorno (una sola vez)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Abre `.env` y pon tus llaves de Gemini separadas por coma:

```
GEMINI_API_KEYS=AIza...uno,AIza...dos,AIza...tres
GEMINI_MODELOS=gemini-2.5-flash
```

Verifica que responden y averigua qué modelos soporta tu llave:

```powershell
.venv\Scripts\python -m src.llm             # prueba cada llave una por una
.venv\Scripts\python -m src.llm --modelos   # lista los modelos disponibles
```

Ese segundo comando le pregunta a la API, así que te da los identificadores
exactos que tu llave puede usar. Pon los que quieras en `GEMINI_MODELOS`, en
orden de preferencia.

### Paso 1 — ver el estado antes de tocar nada

```powershell
.venv\Scripts\python -m ingest.estado
```

Dice cuántas páginas hay en cache, qué falta por descargar por categoría, y con
qué datos está trabajando el agente en este momento. **Córrelo antes y después de
cada paso.** No usa red.

### Paso 2 — descargar (el único paso que usa red)

```powershell
.venv\Scripts\python -m ingest.fetch_all --etapa 1    # 3 categorías, ~27 páginas
.venv\Scripts\python -m ingest.fetch_all --etapa 2    # las 14 del núcleo + 6 de guías
.venv\Scripts\python -m ingest.fetch_all --etapa 3    # las 5 opcionales
```

Lanza **uno solo a la vez**. Dos procesos en paralelo duplican la tasa de requests
y Cloudflare está delante del sitio.

Para verlo en vivo, en otra terminal:

```powershell
while ($true) {
  $n = (Get-ChildItem cache\html -ErrorAction SilentlyContinue).Count
  $u = (Get-Content cache\manifest.jsonl -Tail 1 | ConvertFrom-Json).url
  Write-Host "$n paginas | $($u.Split('/')[-2..-1] -join '/')"
  Start-Sleep 5
}
```

### Paso 3 — parsear (sin red, aquí se itera)

```powershell
.venv\Scripts\python -m ingest.parse_all
```

Lee todo `cache/` y escribe `data/productos.json` y `data/guias.json`. Corre en
segundos, así que cuando ajustes un selector en `ingest/parse.py` repite solo este
paso. Para probar contra una página guardada:

```powershell
.venv\Scripts\python -m ingest.probar_parser
```

### Paso 4 — indexar (de aquí lee el agente)

```powershell
.venv\Scripts\python -m ingest.build_index
```

Sin `--fuente` usa los datos reales. Con `--fuente evals/fixture_productos.json`
vuelve al fixture sintético de 30 productos.

### Paso 5 — QA de los datos

```powershell
.venv\Scripts\python -m ingest.sanity
```

Imprime conteo y rango de precios por categoría, precios sospechosos y porcentaje
de unidad incierta. **Abre a mano los 3 links que imprime al final y compara el
precio.** Eso es lo que separa un dataset real de uno que parece real.

### Paso 6 — semilla versionada

```powershell
.venv\Scripts\python -m ingest.make_seed
```

Crea `data/muestra.json` con ~25 productos. Este sí va al repo, para que los evals
corran en cualquier máquina sin redistribuir el catálogo completo.

### Paso 7 — probar el sistema

```powershell
.venv\Scripts\python -m evals.prove              # 8 componentes, sin API key
.venv\Scripts\python -m evals.prove --con-llm    # incluye los 3 loops agénticos
.venv\Scripts\python run.py --largo 2 --ancho 2 --presupuesto 2000000
.venv\Scripts\python run.py --largo 2 --ancho 2 --presupuesto 2000000 --deterministico
```

### Paso 8 — la mañana del evento, desde EAFIT

```powershell
.venv\Scripts\python -m ingest.healthcheck       # ¿la red de EAFIT permite el PDP?
.venv\Scripts\streamlit run app.py
```

---

## Garantías de reanudación

Qué pasa si vuelves a lanzar cada paso:

| Comando | Reanuda | Qué hace exactamente |
|---|---|---|
| `fetch_all --etapa N` | **Sí** | Si el HTML ya está en cache, **cero requests**. Solo baja lo que falta. Verificado: 132 páginas en cache → 1,5 s y 0 descargas nuevas. |
| `fetch_all --force` | **No** | Re-descarga todo. Úsalo solo para refrescar precios. |
| `parse_all` | Re-deriva | Reescribe los dos JSON desde el cache completo. No pierde nada porque el cache es la fuente. |
| `build_index` | Reconstruye | `DROP TABLE` y vuelve a llenar desde el JSON. Seguro: todo es derivado. |
| `sanity`, `estado`, `probar_parser` | Solo lectura | No escriben nada. |
| `make_seed` | Sobrescribe | Regenera `data/muestra.json`. |

**Lo único que nunca hay que borrar es `cache/`.** Todo lo demás se regenera desde
ahí sin volver a tocar el sitio. Si borras `cache/`, tienes que re-descargar las
132 páginas.

Detalles de robustez en `ingest/fetch.py`:

- El HTML se escribe a `.tmp` y se renombra al final, así que un Ctrl+C no deja una
  página truncada que el parser leería como válida.
- El registro en `manifest.jsonl` es idempotente y también ocurre en los aciertos
  de cache, para que un proceso muerto a mitad no deje archivos huérfanos
  invisibles al parseo. `ingest.estado` reporta huérfanos si aparecen.


## LLM: pool de llaves y cadena de fallback

`src/llm.py` es la única parte del proyecto que sabe qué proveedor hay debajo. Los
agentes hablan con `generar()` en un formato neutro, así que rotar llaves o cambiar
de proveedor no toca ni una línea de `src/supervisor.py` ni de `src/subagentes.py`.

**Orden de intentos:** para cada modelo de `GEMINI_MODELOS`, prueba cada llave
disponible de `GEMINI_API_KEYS`. Si el modelo no existe pasa al siguiente modelo.

**Clasificación de errores**, que es lo que hace útil el fallback:

| Error | Qué hace | Efecto en la llave |
|---|---|---|
| `API key not valid`, 401, 403 | rota a la siguiente llave | **inhabilitada** el resto de la sesión |
| 429, `RESOURCE_EXHAUSTED`, quota | rota a la siguiente llave | enfría `LLM_COOLDOWN_S` segundos (60 por defecto) |
| 500, 503, timeout, `overloaded` | rota a la siguiente llave | enfría 5 segundos |
| 404, `not found` (modelo) | pasa al siguiente **modelo** | no penaliza la llave |

Cuando se agotan llaves y modelos lanza `SinLlavesDisponibles` con el detalle de
cuántos intentos hubo y el último error, en vez de fallar en silencio.

Cada fallback queda registrado en la traza como paso `fallback`, así que en la demo
se ve en pantalla si una llave se cayó y otra la reemplazó.

Para volver a Anthropic sin tocar código: `LLM_PROVEEDOR=anthropic` y
`ANTHROPIC_API_KEY=...` en `.env`.

Verificación sin gastar llamadas reales:

```powershell
.venv\Scripts\python -m evals.prove      # el componente 9 simula 429, 503 y modelo inexistente
```

---

## Arquitectura

Tres loops de piensa→actúa→observa y dos componentes deterministas.

```
Objetivo → Supervisor (loop) ─┬→ Cuantificador (loop, NO ve precios)
                              └→ Comprador (loop, NO ve cantidades)
                                 → Negociador (código) → Verificador (código)
                                 → si rechaza, la falla vuelve al Supervisor
                                   COMO RESULTADO DE HERRAMIENTA
```

La separación en dos sub-agentes no es cosmética: si el mismo agente ve las
medidas y el presupuesto, "descubre" que se necesitan 3.2 m² de cerámica en vez de
4.4 para que la cifra cuadre. `Espacio.sin_presupuesto()` lo impide y
`evals/prove.py` lo verifica en cada corrida.

El Negociador es código y no un LLM porque ajustar N ítems a un tope es
optimización: un LLM complace al usuario y alucina totales. El LLM decide **qué**
recortar proponiendo tres gamas; la aritmética la hace Python y el Verificador la
audita.

## Componentes de arquitectura

| # | Componente | Archivo | Cómo se demuestra |
|---|---|---|---|
| 1 | Guardrails de entrada | `src/schemas.py` | rechaza $200.000 y un baño de 36 m² antes de gastar una llamada al LLM |
| 2 | Retrieval y grounding | `src/catalogo.py` | SQL + FTS5 sobre datos reales; toda cifra con SKU y URL |
| 3 | Cuantificación auditable | `src/reglas.py` | fórmula sustituida en cada requerimiento; el LLM no calcula |
| 4 | Multi-agente aislado | `src/subagentes.py`, `src/tools.py` | el Cuantificador no tiene ninguna herramienta que devuelva precios |
| 5 | Negociación bajo restricción | `src/negociador.py` | recortes explicados en pesos, 93–96% de uso del tope |
| 6 | Auto-corrección | `src/verificador.py` | atrapa SKU inventado, aritmética alterada y omisión de esenciales |
| 7 | Memoria de sesión | `src/memoria.py` | el 2º turno sube el tope y no re-cuantifica |
| 8 | Observabilidad | `src/traza.py`, `evals/` | `python -m evals.prove` → 34 chequeos |

`python -m evals.prove` imprime cada componente haciendo su trabajo, con el
archivo donde vive. Es la respuesta a "¿esto está mockeado?".

## Los datos

Tres capas:

- **A. Snapshot del catálogo.** Páginas de categoría de homecenter.com.co, que
  vienen renderizadas en el servidor. `catId` y slugs tomados del sitemap oficial
  declarado en `robots.txt`. La paginación se reemplaza por **facetas**
  (`f.product.brandName`, `Material`, `Tipo`…), explícitamente permitidas en
  `robots.txt`.
- **B. Corpus de guías.** Los bloques de FAQ y texto técnico al final de cada
  categoría, escritos por Homecenter. El mismo scraper los baja. Es el corpus RAG.
- **C. Validación en vivo.** GET al PDP en el momento de cotizar, con timeout de
  5 s y circuit breaker: tras dos fallos degrada al snapshot y la UI lo dice.

El catálogo **no** va en base vectorial y es a propósito: un embedding no responde
"el más barato bajo $400.000 en porcelana blanca". Texto no estructurado → RAG;
datos con precios y atributos → consulta.

### Respeto al sitio
`ingest/robots.txt` es la copia revisada antes del primer request.
`ingest/fetch.py:permitido()` bloquea las rutas con `Disallow`, incluido el
comodín `/*N-*`. Delay de 1.8 s, `Session` única, User-Agent honesto y sin
rotación. Ante un 403 el scraper se detiene: no evade controles.

### Qué se versiona y qué no
`data/muestra.json` (semilla de ~25 productos) **sí** va al repo, para que los
evals corran en cualquier máquina. El snapshot completo **no**: se regenera con
`python -m ingest.fetch_all && python -m ingest.parse_all`.

## Limitaciones conocidas

- Los precios son un snapshot con fecha, no un feed. La cotización imprime la
  fecha de captura.
- No hay stock por bodega ni por tienda; la disponibilidad es la que publica el
  sitio para Medellín.
- El 10% de merma y los 5 kg/m² de pegante son práctica estándar, **no** están
  verificados contra una guía oficial. El sistema los declara como estimación y la
  UI los muestra en amarillo.
- Cuando no se puede inferir la unidad de venta de un producto, queda marcado
  `unidad_incierta` y el Verificador lo reporta.
- `src/supervisor.py:correr_deterministico` ejecuta los mismos pasos sin el loop
  LLM. Existe como red de seguridad para la demo y está declarado, no escondido.
- Alcance deliberado: un solo espacio (baño). El motor no cambia para cocina;
  cambian las categorías y las reglas.
