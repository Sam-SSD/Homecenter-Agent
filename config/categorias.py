"""Categorias de Homecenter para los 4 ambientes: bano, cocina, habitacion, sala.

catId y slug tomados del sitemap oficial declarado en robots.txt:
https://www.homecenter.com.co/sodimac-catalyst-bu-prod-browse-sitemaps/soco-browse-category-sitemap.xml

Se excluyen a proposito las categorias de campana (precios-campeones, -cmr,
cumpleanos-homecenter, campana-para-padres, mundo-eco, -black, precio-especial,
estrategia-pantallas, latiendavaatucasa, -remodelacion, al-por-mayor,
-cocinas-2026, -producto-personalizado) porque duplican los mismos SKUs y
gastan requests. Tambien se excluyen -infantil, banos-institucionales,
repuestos-*, limpiadores-* y cortadoras (herramienta).

Una categoria puede pertenecer a varios ambientes (pisos_ceramicos y
pintura_interior se venden para bano, cocina, habitacion y sala; la pintura
antihongos es para "banos y cocinas"). Por eso el ambiente NO es un campo de
la categoria ni de la fila de producto: es un mapeo aparte, AMBIENTE_A_CATEGORIAS.
Esto tambien es la razon por la que el esquema de datos/catalogo.db no tiene
columna `ambiente`: forzarla convertiria una relacion N:M en un 1:1 falso.
"""

# cat_id -> (nombre corto, slug, rol). rol="producto" trae productos + facetas;
# rol="guia" es una categoria padre (pagina con FAQ largo, sin productos propios,
# solo corpus de guias).
CATEGORIAS = {
    # --- bano: productos ---
    "cat90040":    ("sanitarios",         "sanitarios-e-inodoros",        "producto"),
    "cat90039":    ("combos_sanitarios",  "combos-sanitarios",            "producto"),
    "cat90041":    ("lavamanos",          "lavamanos",                    "producto"),
    "cat740075":   ("muebles_bano",       "muebles-de-bano",              "producto"),
    "cat960001":   ("muebles_lavamanos",  "muebles-de-bano-con-lavamanos", "producto"),
    "cat740062":   ("griferia_lavamanos", "griferia-para-lavamanos",      "producto"),
    "cat740061":   ("griferia_ducha",     "griferia-para-ducha",          "producto"),
    "cat5070016":  ("pisos_bano",         "pisos-para-bano",              "producto"),
    "cat40494992": ("paredes_ceramicas",  "paredes-ceramicas",            "producto"),
    "cat660036":   ("adhesivo_ceramica",  "adhesivos-para-ceramica",      "producto"),
    "cat660038":   ("boquilla",           "boquillas-fragues-y-pastina",  "producto"),
    "cat10494":    ("pintura_antihongos", "pinturas-antihongos-y-ecologicas-para-banos-y-cocinas", "producto"),
    "cat1900001":  ("divisiones_bano",    "divisiones-de-bano",           "producto"),
    "cat740074":   ("duchas_electricas",  "duchas-electricas",            "producto"),
    "cat740077":   ("espejos_bano",       "espejos-para-banos",           "producto"),
    "cat740079":   ("accesorios_bano",    "accesorios-para-banos",        "producto"),
    "cat740063":   ("columnas_ducha",     "columnas-de-duchas",           "producto"),

    # --- compartidas entre varios ambientes ---
    "cat1640001":  ("pisos_ceramicos",    "pisos-ceramicos",              "producto"),
    "cat1680181":  ("pintura_interior",   "pintura-para-interior",        "producto"),

    # --- cocina: productos ---
    "cat70008":    ("lavaplatos_empotrar",  "lavaplatos-de-empotrar",       "producto"),
    "cat70010":    ("lavaplatos_sobreponer","lavaplatos-de-sobreponer",     "producto"),
    "cat740040":   ("mesones_cocina",       "mesones-de-cocina",            "producto"),
    "cat3260006":  ("mesones_granito",      "mesones-en-granito",           "producto"),
    "cat70014":    ("muebles_cocina",       "gabinetes-y-muebles-de-cocina", "producto"),
    "cat5070017":  ("pisos_cocina",         "pisos-para-cocina",            "producto"),
    "cat10210025": ("griferia_cocina",      "griferias-y-accesorios-de-cocina", "producto"),
    "cat660024":   ("decorados_cocina",     "decorados-para-cocinas",       "producto"),

    # --- habitacion: productos ---
    "cat10308":    ("muebles_habitacion", "muebles-para-habitacion",      "producto"),
    "cat1660049":  ("camas",              "camas",                       "producto"),
    "cat210003":   ("colchones",          "colchones",                   "producto"),
    "cat10310":    ("closets",            "closets-y-armarios",          "producto"),
    "cat5070018":  ("pisos_habitacion",   "pisos-para-sala-comedor-y-habitaciones", "producto"),

    # --- sala: productos ---
    "cat10332":    ("muebles_sala",       "muebles-de-sala-y-estar",      "producto"),
    "cat10334":    ("sofas",              "sofas",                       "producto"),
    "cat10342":    ("comedores",          "comedores",                   "producto"),
    "cat80006":    ("sillas_comedor",     "sillas-de-comedor",            "producto"),
    "cat9670017":  ("iluminacion",        "lamparas-e-iluminacion",       "producto"),

    # --- categorias padre: solo corpus de guias (FAQ y texto tecnico) ---
    "cat70028":    ("banos",              "banos",                        "guia"),
    "cat1770067":  ("bano_cocina_aseo",   "bano-cocina-y-aseo",           "guia"),
    "cat940033":   ("pisos_pinturas",     "pisos-pinturas-y-terminaciones", "guia"),
    "cat40446128": ("sanitarios_combos",  "sanitarios-y-combos-sanitarios", "guia"),
    "cat40683672": ("griferias_banos",    "griferias-para-banos",         "guia"),
    "cat41432114": ("acabados_banos",     "terminaciones-y-acabados-de-banos", "guia"),
    "cat41432125": ("acabados_cocinas",   "terminaciones-y-acabados-de-cocinas", "guia"),
}

# Ambiente -> nombres de categoria (los mismos nombres cortos de CATEGORIAS).
# Una categoria puede repetirse en varios ambientes: eso es lo que soporta la
# multi-pertenencia sin tocar el esquema SQL.
AMBIENTE_A_CATEGORIAS = {
    "bano": [
        "sanitarios", "combos_sanitarios", "lavamanos", "muebles_bano",
        "muebles_lavamanos", "griferia_lavamanos", "griferia_ducha",
        "pisos_bano", "pisos_ceramicos", "paredes_ceramicas",
        "adhesivo_ceramica", "boquilla", "pintura_antihongos",
        "pintura_interior", "divisiones_bano", "duchas_electricas",
        "espejos_bano", "accesorios_bano", "columnas_ducha",
    ],
    "cocina": [
        "lavaplatos_empotrar", "lavaplatos_sobreponer", "mesones_cocina",
        "mesones_granito", "muebles_cocina", "pisos_cocina",
        "griferia_cocina", "decorados_cocina", "pisos_ceramicos",
        "pintura_antihongos", "pintura_interior",
    ],
    "habitacion": [
        "muebles_habitacion", "camas", "colchones", "closets",
        "pisos_habitacion", "pisos_ceramicos", "pintura_interior",
    ],
    "sala": [
        "muebles_sala", "sofas", "comedores", "sillas_comedor",
        "iluminacion", "pisos_ceramicos", "pintura_interior",
    ],
}

# Categorias padre (rol="guia") por ambiente, para bajar solo su corpus RAG.
AMBIENTE_A_GUIAS = {
    "bano": ["banos", "bano_cocina_aseo", "pisos_pinturas", "sanitarios_combos",
             "griferias_banos", "acabados_banos"],
    "cocina": ["bano_cocina_aseo", "pisos_pinturas", "acabados_cocinas"],
    "habitacion": ["pisos_pinturas"],
    "sala": ["pisos_pinturas"],
}

CAT_A_NOMBRE = {k: v[0] for k, v in CATEGORIAS.items()}

# nombre corto -> cat_id, para resolver AMBIENTE_A_CATEGORIAS/GUIAS a cat_ids.
NOMBRE_A_CATID = {v[0]: k for k, v in CATEGORIAS.items()}

# Vistas derivadas equivalentes a las NUCLEO/EXTRA/SOLO_GUIA de antes, por si
# algo externo las necesita: todas las de rol producto y todas las de rol guia.
PRODUCTOS = {k: (v[0], v[1]) for k, v in CATEGORIAS.items() if v[2] == "producto"}
SOLO_GUIA = {k: (v[0], v[1]) for k, v in CATEGORIAS.items() if v[2] == "guia"}


def categorias_de_ambiente(ambiente: str) -> dict:
    """cat_id -> (nombre, slug) de las categorias de producto de un ambiente."""
    nombres = AMBIENTE_A_CATEGORIAS.get(ambiente, [])
    return {NOMBRE_A_CATID[n]: (CATEGORIAS[NOMBRE_A_CATID[n]][0], CATEGORIAS[NOMBRE_A_CATID[n]][1])
            for n in nombres if n in NOMBRE_A_CATID}


def guias_de_ambiente(ambiente: str) -> dict:
    """cat_id -> (nombre, slug) de las categorias padre (solo guias) de un ambiente."""
    nombres = AMBIENTE_A_GUIAS.get(ambiente, [])
    return {NOMBRE_A_CATID[n]: (CATEGORIAS[NOMBRE_A_CATID[n]][0], CATEGORIAS[NOMBRE_A_CATID[n]][1])
            for n in nombres if n in NOMBRE_A_CATID}


# Mapeo concepto de obra -> categorias donde buscar. Sin esto el Comprador
# busca "sanitario" en texto libre y trae limpiadores de sanitario.
CONCEPTO_A_CATEGORIA = {
    # bano
    "ceramica de piso":       ["pisos_bano", "pisos_ceramicos"],
    "ceramica de pared":      ["paredes_ceramicas"],
    "sanitario":              ["sanitarios", "combos_sanitarios"],
    "lavamanos":              ["lavamanos", "muebles_lavamanos"],
    "mueble de bano":         ["muebles_bano", "muebles_lavamanos"],
    "griferia de lavamanos":  ["griferia_lavamanos"],
    "griferia de ducha":      ["griferia_ducha", "columnas_ducha"],
    "pegante para ceramica":  ["adhesivo_ceramica"],
    "boquilla":               ["boquilla"],
    "pintura":                ["pintura_antihongos", "pintura_interior"],
    "division de ducha":      ["divisiones_bano"],
    "espejo":                 ["espejos_bano"],
    # cocina
    "lavaplatos":             ["lavaplatos_empotrar", "lavaplatos_sobreponer"],
    "meson de cocina":        ["mesones_cocina", "mesones_granito"],
    "mueble de cocina":       ["muebles_cocina"],
    "griferia de cocina":     ["griferia_cocina"],
    "ceramica de piso cocina": ["pisos_cocina", "pisos_ceramicos"],
    # habitacion
    "cama":                   ["camas"],
    "colchon":                ["colchones"],
    "closet":                 ["closets"],
    "ceramica de piso habitacion": ["pisos_habitacion", "pisos_ceramicos"],
    # sala
    "sofa":                   ["sofas", "muebles_sala"],
    "comedor":                ["comedores"],
    "silla de comedor":       ["sillas_comedor"],
    "lampara":                ["iluminacion"],
}

# Las categorias de Homecenter incluyen accesorios y repuestos: la categoria
# "griferia-para-lavamanos" tiene sifones y desagues, y "pisos-para-bano" tiene
# ceramica de pared. Sin este filtro la gama economica de cada concepto termina
# siendo el accesorio mas barato de la categoria, no el producto que se pidio.
# `debe`: el nombre tiene que contener al menos uno.  `no`: descarta si aparece.
CONCEPTO_FILTROS = {
    "ceramica de piso": {
        "debe": ["piso", "porcelanato", "porcelanico", "baldosa", "ceramica"],
        "no": ["pared", "muro", "guardaescoba", "listelo", "cenefa", "peldano"],
    },
    "ceramica de pared": {
        "debe": ["pared", "muro", "revestimiento", "ceramica", "porcelanato"],
        "no": ["piso", "guardaescoba", "peldano"],
    },
    "sanitario": {
        "debe": ["sanitario", "inodoro", "combo"],
        "no": ["asiento", "tapa", "repuesto", "valvula", "tanque", "limpiador",
               "cepillo", "chupa", "grifo", "kit"],
    },
    "lavamanos": {
        "debe": ["lavamanos", "lavabo"],
        "no": ["griferia", "grifo", "sifon", "desague", "repuesto", "pedestal solo",
               "mueble", "espejo", "kit"],
    },
    "mueble de bano": {
        "debe": ["mueble", "gabinete", "vanitorio"],
        "no": ["repuesto", "bisagra", "herraje", "correder"],
    },
    "griferia de lavamanos": {
        "debe": ["griferia", "grifo", "monomando", "monocontrol", "mezclador", "llave"],
        "no": ["sifon", "desague", "repuesto", "kit de instalacion", "manguera",
               "acople", "cartucho", "aireador"],
    },
    "griferia de ducha": {
        "debe": ["griferia", "grifo", "monomando", "mezclador", "ducha", "regadera",
                 "columna", "teleducha"],
        "no": ["repuesto", "manguera sola", "cartucho", "cortina", "asiento",
               "barra de seguridad", "tapete"],
    },
    "pegante para ceramica": {
        "debe": ["pegante", "adhesivo", "mortero", "bondex"],
        "no": ["silicona", "sellante", "limpiador", "removedor"],
    },
    "boquilla": {
        "debe": ["boquilla", "fragua", "pastina", "junta"],
        "no": ["limpiador", "aplicador", "pistola", "removedor"],
    },
    "pintura": {
        "debe": ["pintura", "vinilo", "esmalte"],
        "no": ["brocha", "rodillo", "bandeja", "cinta", "lija", "removedor",
               "diluyente", "thinner", "estuco", "aerosol"],
    },
    "division de ducha": {
        "debe": ["division", "cabina", "mampara", "puerta de ducha"],
        "no": ["repuesto", "riel solo", "cortina"],
    },
    "espejo": {"debe": ["espejo"], "no": ["repuesto", "adhesivo"]},
    "lavaplatos": {
        "debe": ["lavaplatos", "lavaplato"],
        "no": ["griferia", "grifo", "repuesto", "sifon", "desague", "escurridor"],
    },
    "meson de cocina": {
        "debe": ["meson"],
        "no": ["repuesto", "soporte solo"],
    },
    "mueble de cocina": {
        "debe": ["mueble", "gabinete", "modulo"],
        "no": ["repuesto", "bisagra", "herraje", "correder", "organizador"],
    },
    "griferia de cocina": {
        "debe": ["griferia", "grifo", "monomando", "mezclador"],
        "no": ["sifon", "desague", "repuesto", "manguera", "cartucho", "aireador"],
    },
    "ceramica de piso cocina": {
        "debe": ["piso", "porcelanato", "porcelanico", "baldosa", "ceramica"],
        "no": ["pared", "muro", "guardaescoba", "listelo", "cenefa"],
    },
    "cama": {"debe": ["cama", "base cama", "espaldar"], "no": ["repuesto", "sabana", "cobija"]},
    "colchon": {"debe": ["colchon"], "no": ["protector", "funda", "repuesto"]},
    "closet": {"debe": ["closet", "armario"], "no": ["organizador", "repuesto", "herraje", "bisagra"]},
    "ceramica de piso habitacion": {
        "debe": ["piso", "porcelanato", "porcelanico", "baldosa", "ceramica", "laminado"],
        "no": ["pared", "muro", "guardaescoba", "listelo", "cenefa"],
    },
    "sofa": {"debe": ["sofa", "sofa cama", "poltrona"], "no": ["repuesto", "funda", "cojin"]},
    "comedor": {"debe": ["comedor", "mesa"], "no": ["repuesto", "mantel", "individual"]},
    "silla de comedor": {"debe": ["silla"], "no": ["repuesto", "cojin", "funda"]},
    "lampara": {"debe": ["lampara", "luminaria", "bombillo"], "no": ["repuesto", "pantalla sola"]},
}
