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
