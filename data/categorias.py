"""Categorias de Homecenter para el mundo bano.

catId y slug tomados del sitemap oficial declarado en robots.txt:
https://www.homecenter.com.co/sodimac-catalyst-bu-prod-browse-sitemaps/soco-browse-category-sitemap.xml

Se excluyen a proposito las categorias de campana (precios-campeones, -cmr,
cumpleanos-homecenter, campana-para-padres, mundo-eco, -black, precio-especial,
estrategia-pantallas, latiendavaatucasa, -remodelacion, al-por-mayor) porque
duplican los mismos SKUs y gastan requests. Tambien se excluyen -infantil,
banos-institucionales, repuestos-*, limpiadores-* y cortadoras (herramienta).
"""

NUCLEO = {
    "cat90040":    ("sanitarios",         "sanitarios-e-inodoros"),
    "cat90039":    ("combos_sanitarios",  "combos-sanitarios"),
    "cat90041":    ("lavamanos",          "lavamanos"),
    "cat740075":   ("muebles_bano",       "muebles-de-bano"),
    "cat960001":   ("muebles_lavamanos",  "muebles-de-bano-con-lavamanos"),
    "cat740062":   ("griferia_lavamanos", "griferia-para-lavamanos"),
    "cat740061":   ("griferia_ducha",     "griferia-para-ducha"),
    "cat5070016":  ("pisos_bano",         "pisos-para-bano"),
    "cat1640001":  ("pisos_ceramicos",    "pisos-ceramicos"),
    "cat40494992": ("paredes_ceramicas",  "paredes-ceramicas"),
    "cat660036":   ("adhesivo_ceramica",  "adhesivos-para-ceramica"),
    "cat660038":   ("boquilla",           "boquillas-fragues-y-pastina"),
    "cat10494":    ("pintura_antihongos", "pinturas-antihongos-y-ecologicas-para-banos-y-cocinas"),
    "cat1680181":  ("pintura_interior",   "pintura-para-interior"),
}

EXTRA = {
    "cat1900001":  ("divisiones_bano",    "divisiones-de-bano"),
    "cat740074":   ("duchas_electricas",  "duchas-electricas"),
    "cat740077":   ("espejos_bano",       "espejos-para-banos"),
    "cat740079":   ("accesorios_bano",    "accesorios-para-banos"),
    "cat740063":   ("columnas_ducha",     "columnas-de-duchas"),
}

# Categorias padre: solo corpus de guias (FAQ y texto tecnico), no productos.
SOLO_GUIA = {
    "cat70028":    ("banos",              "banos"),
    "cat1770067":  ("bano_cocina_aseo",   "bano-cocina-y-aseo"),
    "cat940033":   ("pisos_pinturas",     "pisos-pinturas-y-terminaciones"),
    "cat40446128": ("sanitarios_combos",  "sanitarios-y-combos-sanitarios"),
    "cat40683672": ("griferias_banos",    "griferias-para-banos"),
    "cat41432114": ("acabados_banos",     "terminaciones-y-acabados-de-banos"),
}

CAT_A_NOMBRE = {k: v[0] for k, v in {**NUCLEO, **EXTRA, **SOLO_GUIA}.items()}

# Mapeo concepto de obra -> categorias donde buscar. Sin esto el Comprador
# busca "sanitario" en texto libre y trae limpiadores de sanitario.
CONCEPTO_A_CATEGORIA = {
    "ceramica de piso":      ["pisos_bano", "pisos_ceramicos"],
    "ceramica de pared":     ["paredes_ceramicas"],
    "sanitario":             ["sanitarios", "combos_sanitarios"],
    "lavamanos":             ["lavamanos", "muebles_lavamanos"],
    "mueble de bano":        ["muebles_bano", "muebles_lavamanos"],
    "griferia de lavamanos": ["griferia_lavamanos"],
    "griferia de ducha":     ["griferia_ducha", "columnas_ducha"],
    "pegante para ceramica": ["adhesivo_ceramica"],
    "boquilla":              ["boquilla"],
    "pintura":               ["pintura_antihongos", "pintura_interior"],
    "division de ducha":     ["divisiones_bano"],
    "espejo":                ["espejos_bano"],
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
}
