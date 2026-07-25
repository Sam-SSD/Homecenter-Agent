# Cotizador de remodelación — Homecenter

Sistema agéntico que cuantifica materiales de obra contra las guías técnicas
publicadas por Homecenter, busca productos reales en su catálogo, y **negocia
recortes cuando no alcanza el presupuesto** en vez de complacer al usuario.
Cubre cuatro ambientes: baño, cocina, habitación y sala.

AgentSprint by ReshapeX · Universidad EAFIT · Medellín · 25 de julio de 2026

---

## Estructura de carpetas

```
dominio/    modelos (Espacio, Producto, Requerimiento...), reglas de obra,
            catalogo (SQL + FTS5), negociador, verificador, memoria, traza, y
            el pipeline determinista (nucleo.py). Codigo puro, sin LLM.
agentes/    los 3 loops LLM (supervisor, subagentes, qa), el proveedor de LLM
            aislado (llm.py), prompts, tools, y el arranque unificado (ejecutar.py).
config/     fuente versionada: categorias de Homecenter (categorias.py) y las
            reglas de cuantificacion de obra (reglas_obra.yaml).
datos/      artefactos generados y gitignored: catalogo.db, productos.json,
            guias.json, memoria.db. Se regeneran del pipeline de ingesta.
ingesta/    scraping y parseo (fetch, parse, build_index, sanity, estado,
            healthcheck, probar_parser).
pruebas/    prove.py (145 chequeos), cases.yaml, fixture_productos.json,
            fixtures/ (datos de prueba: dump del sitemap, HTML de ejemplo).
run.py, app.py   entrypoints, en la raiz del repo (streamlit y python ponen el
                 directorio del script en sys.path, asi que no viven en una
                 subcarpeta sin romper sus imports).
```

El ambiente (baño/cocina/habitación/sala) no es una carpeta ni una columna en
la base de datos: vive en el mapeo concepto→categoría de `config/categorias.py`
y en el campo `ambientes` de cada regla en `config/reglas_obra.yaml`. Una misma
categoría de producto (p. ej. `pisos_ceramicos`) puede pertenecer a varios
ambientes.

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
.venv\Scripts\python -m agentes.llm             # prueba cada llave una por una
.venv\Scripts\python -m agentes.llm --modelos   # lista los modelos disponibles
```

Ese segundo comando le pregunta a la API, así que te da los identificadores
exactos que tu llave puede usar. Pon los que quieras en `GEMINI_MODELOS`, en
orden de preferencia.

### Paso 1 — ver el estado antes de tocar nada

```powershell
.venv\Scripts\python -m ingesta.estado
```

Dice cuántas páginas hay en cache, qué falta por descargar por categoría, y con
qué datos está trabajando el agente en este momento. **Córrelo antes y después de
cada paso.** No usa red.

### Paso 2 — descargar (el único paso que usa red)

```powershell
.venv\Scripts\python -m ingesta.fetch_all --ambiente bano
.venv\Scripts\python -m ingesta.fetch_all --ambiente cocina
.venv\Scripts\python -m ingesta.fetch_all --ambiente habitacion
.venv\Scripts\python -m ingesta.fetch_all --ambiente sala
# o los 4 de una vez:
.venv\Scripts\python -m ingesta.fetch_all --ambiente todos
```

Antes de lanzar, estima cuántos requests toma (cero red):

```powershell
.venv\Scripts\python -m ingesta.fetch_all --ambiente cocina --estimar
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
.venv\Scripts\python -m ingesta.parse_all
```

Lee todo `cache/` y escribe `datos/productos.json` y `datos/guias.json`. Corre en
segundos, así que cuando ajustes un selector en `ingesta/parse.py` repite solo este
paso. Para probar contra una página guardada:

```powershell
.venv\Scripts\python -m ingesta.probar_parser
```

### Paso 4 — indexar (de aquí lee el agente)

```powershell
.venv\Scripts\python -m ingesta.build_index
```

Sin `--fuente` usa los datos reales. Con `--fuente pruebas/fixture_productos.json`
vuelve al fixture sintético de los 4 ambientes.

### Paso 5 — QA de los datos

```powershell
.venv\Scripts\python -m ingesta.sanity
```

Imprime conteo y rango de precios por categoría, precios sospechosos y porcentaje
de unidad incierta. **Abre a mano los 3 links que imprime al final y compara el
precio.** Eso es lo que separa un dataset real de uno que parece real.

### Paso 6 — probar el sistema

```powershell
.venv\Scripts\python -m pruebas.prove              # nucleo determinista, sin API key
.venv\Scripts\python -m pruebas.prove --con-llm    # + los 3 loops agenticos (solo bano, cuota limitada)
.venv\Scripts\python run.py --tipo bano --largo 2 --ancho 2 --presupuesto 2000000
.venv\Scripts\python run.py --tipo cocina --largo 3 --ancho 2.5 --presupuesto 8000000 --deterministico
```

Los evals sin red usan `pruebas/fixture_productos.json` (trackeado en el repo, con
productos sintéticos de los 4 ambientes) si no hay `datos/catalogo.db` construido
desde datos reales todavía.

### Paso 7 — la mañana del evento, desde EAFIT

```powershell
.venv\Scripts\python -m ingesta.healthcheck       # ¿la red de EAFIT permite el PDP? (bano)
.venv\Scripts\streamlit run app.py
```

---

## Garantías de reanudación

Qué pasa si vuelves a lanzar cada paso:

| Comando | Reanuda | Qué hace exactamente |
|---|---|---|
| `fetch_all --ambiente X` | **Sí** | Si el HTML ya está en cache, **cero requests**. Solo baja lo que falta. |
| `fetch_all --force` | **No** | Re-descarga todo. Úsalo solo para refrescar precios. |
| `parse_all` | Re-deriva | Reescribe los dos JSON desde el cache completo. No pierde nada porque el cache es la fuente. |
| `build_index` | Reconstruye | `DROP TABLE` y vuelve a llenar desde el JSON. Seguro: todo es derivado. |
| `sanity`, `estado`, `probar_parser` | Solo lectura | No escriben nada. |

**Lo único que nunca hay que borrar es `cache/`.** Todo lo demás se regenera desde
ahí sin volver a tocar el sitio.

Detalles de robustez en `ingesta/fetch.py`:

- El HTML se escribe a `.tmp` y se renombra al final, así que un Ctrl+C no deja una
  página truncada que el parser leería como válida.
- El registro en `manifest.jsonl` es idempotente y también ocurre en los aciertos
  de cache, para que un proceso muerto a mitad no deje archivos huérfanos
  invisibles al parseo. `ingesta.estado` reporta huérfanos si aparecen.


## LLM: pool de llaves y cadena de fallback

`agentes/llm.py` es la única parte del proyecto que sabe qué proveedor hay debajo.
Los agentes hablan con `generar()` en un formato neutro, así que rotar llaves o
cambiar de proveedor no toca ni una línea de `agentes/supervisor.py` ni de
`agentes/subagentes.py`.

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
.venv\Scripts\python -m pruebas.prove      # el componente 9 simula 429, 503 y modelo inexistente
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
`pruebas/prove.py` lo verifica en cada corrida.

El Negociador es código y no un LLM porque ajustar N ítems a un tope es
optimización: un LLM complace al usuario y alucina totales. El LLM decide **qué**
recortar proponiendo tres gamas; la aritmética la hace Python y el Verificador la
audita.

## Componentes de arquitectura

| # | Componente | Archivo | Cómo se demuestra |
|---|---|---|---|
| 1 | Guardrails de entrada | `dominio/schemas.py` | rechaza $200.000 y un baño de 36 m² antes de gastar una llamada al LLM; los límites de área/lado/presupuesto son por ambiente (`LIMITES`) |
| 2 | Retrieval y grounding | `dominio/catalogo.py` | SQL + FTS5 sobre datos reales; toda cifra con SKU y URL |
| 3 | Cuantificación auditable | `dominio/reglas.py` | fórmula sustituida en cada requerimiento; el LLM no calcula; reglas filtradas por ambiente |
| 4 | Multi-agente aislado | `agentes/subagentes.py`, `agentes/tools.py` | el Cuantificador no tiene ninguna herramienta que devuelva precios |
| 5 | Negociación bajo restricción | `dominio/negociador.py` | recortes explicados en pesos; fases de obra por el campo `fase` de cada regla |
| 6 | Auto-corrección | `dominio/verificador.py` | atrapa SKU inventado, aritmética alterada y omisión de esenciales (por ambiente) |
| 7 | Memoria de sesión | `dominio/memoria.py` | el 2º turno sube el tope y no re-cuantifica |
| 8 | Observabilidad | `dominio/traza.py`, `pruebas/` | `python -m pruebas.prove` → 145 chequeos, incluidos dos que verifican que cada regla del YAML tiene fórmula bien formada y resuelve a producto real en su ambiente |

`python -m pruebas.prove` imprime cada componente haciendo su trabajo, con el
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
`ingesta/robots_homecenter_2026-07-24.txt` es la copia revisada antes del primer request.
`ingesta/fetch.py:permitido()` bloquea las rutas con `Disallow`, incluido el
comodín `/*N-*`. Delay de 1.8 s, `Session` única, User-Agent honesto y sin
rotación. Ante un 403 el scraper se detiene: no evade controles.

### Qué se versiona y qué no
`pruebas/fixture_productos.json` (productos sintéticos de los 4 ambientes) **sí**
va al repo, para que los evals corran en cualquier máquina sin red.
`config/categorias.py` y `config/reglas_obra.yaml` **sí** van al repo: son la
fuente versionada de los ambientes. El snapshot completo
(`datos/productos.json`, `datos/guias.json`, `datos/catalogo.db`) **no**:
se regenera con `python -m ingesta.fetch_all --ambiente <X> && python -m ingesta.parse_all`.

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
- `agentes/supervisor.py:correr_deterministico` ejecuta los mismos pasos sin el loop
  LLM. Existe como red de seguridad para la demo y está declarado, no escondido.
- Cuatro ambientes (baño, cocina, habitación, sala). El motor no cambia entre
  ellos: cambian las categorías (`config/categorias.py`), las reglas de obra
  (`config/reglas_obra.yaml`, campo `ambientes`) y los límites de guardrail
  (`dominio/schemas.py:LIMITES`). El esquema de `datos/catalogo.db` es el mismo
  para los 4: el ambiente vive en el mapeo concepto→categoría, no en la fila de
  producto (una categoría como `pisos_ceramicos` se vende para varios ambientes).
- `--con-llm` de `pruebas/prove.py` se mantiene solo en baño: la cuota Gemini del
  tier gratuito es 20 requests/día **por modelo**, y esta corrida gasta ~35.
  Cocina, habitación y sala se cubren con los chequeos deterministas (incluido
  el que verifica que cada regla resuelve a producto real en su ambiente).
- La conversión de metros lineales (`ml`) a unidades de venta en
  `dominio/schemas.py:unidades_necesarias` cae al fallback genérico
  (`ceil(cantidad)`): para `meson_cocina`, un producto vendido por centímetro
  lineal puede sobre-redondear la cantidad de unidades a comprar. Detectado,
  no bloquea la demo, pendiente de ajuste.
