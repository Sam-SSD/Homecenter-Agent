# CLAUDE.md — contexto para Claude Code

## Qué es
Cotizador de remodelación de baño con productos reales de Homecenter Colombia.
Hackathon AgentSprint by ReshapeX, EAFIT Medellín, 25-jul-2026, 8:00–12:00.

Frase del pitch: **no es un buscador de productos, es un cuantificador de obra que
negocia con tu presupuesto y te dice que no.**

## Reglas del proyecto — no las rompas

1. **El LLM nunca hace aritmética.** Llama `calcular_cantidad`; Python evalúa la
   fórmula de `data/reglas_obra.yaml` y devuelve la fórmula sustituida.
2. **El LLM nunca inventa un SKU.** Todo producto sale de `buscar_catalogo`.
   `src/subagentes.py:comprar` descarta cualquier SKU que no exista y lo registra.
3. **Aislamiento de información.** El Cuantificador NO ve el presupuesto
   (`Espacio.sin_presupuesto()`) ni tiene herramientas de precio. El Comprador NO
   ve cantidades. Si lo rompes, el sistema ajusta las cantidades para que quepan y
   la cotización en obra no alcanza. `evals/prove.py` lo verifica.
4. **El presupuestador es determinista.** `src/negociador.py` es optimización, no
   un LLM. Un LLM complace y alucina totales.
5. **Toda cifra declara fuente.** Regla sin fuente verificada → `regla_verificada:
   false` → amarillo en la UI. No la marques `true` sin una guía real en
   `data/guias.json`.
6. **Respeta robots.txt.** `ingest/fetch.py:permitido()` bloquea las rutas
   prohibidas. No uses `/search`, no rotes el User-Agent, no evadas Cloudflare.
   Usa la `Session` (conserva la cookie `__cf_bm`). DELAY mínimo 1.8 s.
7. **Descarga y parseo separados.** El parser se itera contra `cache/`, sin red.

## Arquitectura
```
Objetivo → Supervisor (loop) ─┬→ Cuantificador (loop, sin precios)
                              └→ Comprador (loop, sin cantidades)
                                 → Negociador (código) → Verificador (código)
                                 → si rechaza, vuelve al Supervisor como
                                   resultado de herramienta
```
El Q&A (`src/qa.py`) es la única puerta de salida de texto: sin fuente responde
"No tengo información verificada sobre eso."

## Comandos
```bash
cp .env.example .env                                  # poner ANTHROPIC_API_KEY

# datos (requiere red; hacerlo la noche anterior)
python -m ingest.fetch_all --etapa 1                  # 3 categorías, desbloquea al equipo
python -m ingest.fetch_all --etapa 2                  # núcleo completo + guías
python -m ingest.parse_all                            # offline, itera aquí
python -m ingest.build_index
python -m ingest.sanity                               # QA: abre los 3 links que imprime
python -m ingest.make_seed                            # data/muestra.json (sí se commitea)
python -m ingest.healthcheck                          # correr otra vez 7:45 desde EAFIT

# sin red / sin API key
python -m ingest.build_index --fuente evals/fixture_productos.json
python -m evals.prove                                 # 34 chequeos, 8 componentes
python run.py --largo 2 --ancho 2 --presupuesto 2000000 --deterministico

# completo
python -m evals.prove --con-llm
python run.py --largo 2 --ancho 2 --presupuesto 2000000
streamlit run app.py
```

## Estado actual
- Núcleo determinista: **funcionando**, 34/34 en `prove.py` contra el fixture.
- Loops LLM: escritos, **sin probar con API key**. Es la primera tarea.
- `data/catalogo.db` está construido desde `evals/fixture_productos.json`
  (30 productos sintéticos). Reconstruir con datos reales cambia todo lo demás sin
  tocar código: el contrato es la base de datos.
- `data/guias.json` **vacío**: el corpus RAG sale de `ingest.fetch_all --etapa 2`.
  Sin él, `consultar_guia` devuelve "sin fuente verificada" y no se alcanza el
  nivel 4 de la rúbrica.

## Orden de trabajo mañana
- 8:00–8:20 congelar `src/schemas.py`, repartir archivos sin solaparse
- 8:20–9:20 `python -m evals.prove --con-llm` en verde (los 3 loops corriendo)
- 9:20–10:10 corpus de guías real + citaciones + Q&A
- 10:10–10:30 revisar `prove.py`, agregar chequeos que falten
- 10:30 punto de decisión: si el agéntico está frágil, se presenta el determinista
- 10:30–11:20 UI, memoria, aprobación humana
- 11:20 congelar. `git tag demo`. Dos ensayos con cronómetro.

## Verificar antes del evento
- El string del modelo en `.env` (`MODELO=claude-sonnet-5`) contra la doc vigente.
- El parámetro de paginación de las categorías: **no confirmado**. Por eso
  `ingest/fetch.py` usa facetas (permitidas en robots.txt) en vez de paginar.
