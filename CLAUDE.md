# CLAUDE.md â€” contexto para Claude Code

## QuÃ© es
Cotizador de remodelaciÃ³n de baÃ±o con productos reales de Homecenter Colombia.
Hackathon AgentSprint by ReshapeX, EAFIT MedellÃ­n, 25-jul-2026, 8:00â€“12:00.

Frase del pitch: **no es un buscador de productos, es un cuantificador de obra que
negocia con tu presupuesto y te dice que no.**

## Reglas del proyecto â€” no las rompas

1. **El LLM nunca hace aritmÃ©tica.** Llama `calcular_cantidad`; Python evalÃºa la
   fÃ³rmula de `data/reglas_obra.yaml` y devuelve la fÃ³rmula sustituida.
2. **El LLM nunca inventa un SKU.** Todo producto sale de `buscar_catalogo`.
   `src/subagentes.py:comprar` descarta cualquier SKU que no exista y lo registra.
3. **Aislamiento de informaciÃ³n.** El Cuantificador NO ve el presupuesto
   (`Espacio.sin_presupuesto()`) ni tiene herramientas de precio. El Comprador NO
   ve cantidades. Si lo rompes, el sistema ajusta las cantidades para que quepan y
   la cotizaciÃ³n en obra no alcanza. `evals/prove.py` lo verifica.
4. **El presupuestador es determinista.** `src/negociador.py` es optimizaciÃ³n, no
   un LLM. Un LLM complace y alucina totales.
5. **Toda cifra declara fuente.** Regla sin fuente verificada â†’ `regla_verificada:
   false` â†’ amarillo en la UI. No la marques `true` sin una guÃ­a real en
   `data/guias.json`.
6. **Respeta robots.txt.** `ingest/fetch.py:permitido()` bloquea las rutas
   prohibidas. No uses `/search`, no rotes el User-Agent, no evadas Cloudflare.
   Usa la `Session` (conserva la cookie `__cf_bm`). DELAY mÃ­nimo 1.8 s.
7. **Descarga y parseo separados.** El parser se itera contra `cache/`, sin red.

8. **El proveedor de LLM vive solo en `src/llm.py`.** Los agentes usan `generar()`
   en formato neutro. Si necesitas cambiar de modelo o de proveedor, se toca ese
   archivo o `.env`, nunca `supervisor.py` ni `subagentes.py`. Pool de llaves con
   rotacion ante 429/503/llave invalida, y cadena de modelos ante 404.

## Arquitectura
```
Objetivo â†’ Supervisor (loop) â”€â”¬â†’ Cuantificador (loop, sin precios)
                              â””â†’ Comprador (loop, sin cantidades)
                                 â†’ Negociador (cÃ³digo) â†’ Verificador (cÃ³digo)
                                 â†’ si rechaza, vuelve al Supervisor como
                                   resultado de herramienta
```
El Q&A (`src/qa.py`) es la Ãºnica puerta de salida de texto: sin fuente responde
"No tengo informaciÃ³n verificada sobre eso."

## Comandos
```bash
Copy-Item .env.example .env      # poner GEMINI_API_KEYS=llave1,llave2,llave3
python -m src.llm                # verifica cada llave (barato)
python -m src.llm --tools        # + ida y vuelta con herramienta (2 requests, una vez)
python -m src.llm --modelos      # que modelos soporta tu llave (gratis)

# datos (requiere red; hacerlo la noche anterior)
python -m ingest.fetch_all --etapa 1                  # 3 categorÃ­as, desbloquea al equipo
python -m ingest.fetch_all --etapa 2                  # nÃºcleo completo + guÃ­as
python -m ingest.parse_all                            # offline, itera aquÃ­
python -m ingest.build_index
python -m ingest.sanity                               # QA: abre los 3 links que imprime
python -m ingest.make_seed                            # data/muestra.json (sÃ­ se commitea)
python -m ingest.healthcheck                          # correr otra vez 7:45 desde EAFIT

# sin red / sin API key
python -m ingest.build_index --fuente evals/fixture_productos.json
python -m evals.prove                                 # 54 chequeos, 10 componentes
python run.py --largo 2 --ancho 2 --presupuesto 2000000 --deterministico

# completo
python -m evals.prove --con-llm
python run.py --largo 2 --ancho 2 --presupuesto 2000000
streamlit run app.py
```

## Estado actual
- NÃºcleo determinista: **funcionando**, 54/54 en `prove.py` contra el fixture.
- Loops LLM: **probados con llave real**, 58/58 con `--con-llm`. Flujo completo:
  12 requerimientos â†’ 11 conceptos â†’ $1.995.400 de tope $2.000.000, aprobado
  por el verificador sin fallas.
- Cuota Gemini del tier gratuito: **20 requests por dÃ­a y POR MODELO**. Una
  corrida `--con-llm` gasta ~35, asÃ­ que `GEMINI_MODELOS` lleva 4 modelos: el
  fallback por modelo es lo que sostiene el dÃ­a de demo. MÃ¡s llaves = mÃ¡s cupo.
- `data/catalogo.db` estÃ¡ construido desde `evals/fixture_productos.json`
  (30 productos sintÃ©ticos). Reconstruir con datos reales cambia todo lo demÃ¡s sin
  tocar cÃ³digo: el contrato es la base de datos.
- `data/guias.json` **vacÃ­o**: el corpus RAG sale de `ingest.fetch_all --etapa 2`.
  Sin Ã©l, `consultar_guia` devuelve "sin fuente verificada" y no se alcanza el
  nivel 4 de la rÃºbrica.

## Orden de trabajo maÃ±ana
- 8:00â€“8:20 congelar `src/schemas.py`, repartir archivos sin solaparse
- 8:20â€“9:20 `python -m evals.prove --con-llm` en verde (los 3 loops corriendo)
- 9:20â€“10:10 corpus de guÃ­as real + citaciones + Q&A
- 10:10â€“10:30 revisar `prove.py`, agregar chequeos que falten
- 10:30 punto de decisiÃ³n: si el agÃ©ntico estÃ¡ frÃ¡gil, se presenta el determinista
- 10:30â€“11:20 UI, memoria, aprobaciÃ³n humana
- 11:20 congelar. `git tag demo`. Dos ensayos con cronÃ³metro.

## Verificar antes del evento
- Los modelos en `.env` (`GEMINI_MODELOS`): ya verificados el 24-jul-2026 contra
  la llave real (3.6-flash, 3.5-flash-lite, 3.1-flash-lite, 3-flash-preview).
  2.0 y 2.5 estan apagados. Si cambia la llave, corre `python -m src.llm --modelos`.
- `python -m src.llm --tools` hace una ida y vuelta con herramienta: si eso pasa,
  los loops corren (el ping de un solo turno no cubria el bug de las firmas).
  **Cuesta 2 requests del primer modelo, de 20 que hay al dia: corrolo UNA vez.**
- **Conseguir mas llaves.** Con una sola, una corrida `--con-llm` casi agota el
  dia. Cada llave del equipo multiplica el cupo (20/dia x modelo x llave).
- El parÃ¡metro de paginaciÃ³n de las categorÃ­as: **no confirmado**. Por eso
  `ingest/fetch.py` usa facetas (permitidas en robots.txt) en vez de paginar.



