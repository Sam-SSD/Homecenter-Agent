# Cotizador de remodelación de baño — Homecenter

Sistema agéntico que cuantifica materiales de obra contra las guías técnicas
publicadas por Homecenter, busca productos reales en su catálogo, y **negocia
recortes cuando no alcanza el presupuesto** en vez de complacer al usuario.

AgentSprint by ReshapeX · Universidad EAFIT · Medellín · 25 de julio de 2026

---

## Arranque rápido

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # poner ANTHROPIC_API_KEY

# sin red y sin API key: núcleo determinista sobre el fixture
python -m ingest.build_index --fuente evals/fixture_productos.json
python -m evals.prove
python run.py --largo 2 --ancho 2 --presupuesto 2000000 --deterministico

# con datos reales
python -m ingest.fetch_all --etapa 2 && python -m ingest.parse_all
python -m ingest.build_index && python -m ingest.sanity
python -m evals.prove --con-llm
streamlit run app.py
```

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
