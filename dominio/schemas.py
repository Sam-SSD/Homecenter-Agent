"""Contratos del sistema. CONGELAR a las 8:20 AM: todo el equipo codifica contra
esto en paralelo.

Los validadores de este archivo son el componente "guardrails de entrada":
rechazan datos incoherentes antes de gastar una sola llamada al LLM.
"""
from __future__ import annotations
from datetime import datetime, timezone
from math import ceil
from typing import Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


def ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Producto(BaseModel):
    sku: str
    nombre: str
    marca: str = ""
    categoria: str
    cat_id: str = ""
    precio: int = Field(gt=0)
    precio_antes: Optional[int] = None
    unidad: str = "Und"
    m2_por_caja: Optional[float] = None
    kg_por_bulto: Optional[float] = None
    rendimiento_m2: Optional[float] = None
    unidad_incierta: bool = False
    url: str = ""
    imagen_url: Optional[str] = None
    capturado_en: str = ""
    specs: dict[str, str] = Field(default_factory=dict)
    rating: Optional[float] = None
    total_reviews: Optional[int] = None
    modelo: str = ""

    def contenido_por_unidad(self) -> Optional[float]:
        return self.m2_por_caja or self.kg_por_bulto or self.rendimiento_m2


# Guardrails por tipo de ambiente. area_max/lado_max: una sala o comedor
# integrado supera legitimamente los 25 m2 y los 8 m de lado de un bano;
# presupuesto_min: calibrado al item mas barato que ese ambiente no puede
# omitir (el sanitario para bano, un colchon basico para habitacion, etc).
LIMITES: dict[str, dict[str, float]] = {
    "bano":       {"area_max": 25,  "lado_max": 8,  "presupuesto_min": 500_000},
    "cocina":     {"area_max": 40,  "lado_max": 10, "presupuesto_min": 1_500_000},
    "habitacion": {"area_max": 45,  "lado_max": 12, "presupuesto_min": 800_000},
    "sala":       {"area_max": 60,  "lado_max": 14, "presupuesto_min": 1_000_000},
}
PRESUPUESTO_MAX = 200_000_000

# Defaults por tipo para los campos que antes tenian un default global (2.0 de
# enchape, True de ducha). Sin esto, construir un Espacio de bano sin pasar
# altura_enchape_m/incluye_ducha explicitos deja esas reglas sin variable y el
# Cuantificador pierde 3 conceptos (enchape, adhesivo, boquilla) en silencio:
# le paso exactamente eso al loop LLM real antes de este fix. Va en un
# validador "before" (no en _coherencia) para que el default exista ANTES de
# la comparacion altura_enchape_m > altura_m.
DEFAULTS_POR_TIPO: dict[str, dict] = {
    "bano": {"altura_enchape_m": 2.0, "incluye_ducha": True},
    "cocina": {"altura_enchape_m": 2.0, "metros_lineales": 3.0},
    "habitacion": {"metros_lineales": 3.0},
    "sala": {},
}


class Espacio(BaseModel):
    """GUARDRAIL: rechaza medidas y presupuestos incoherentes."""
    tipo: Literal["bano", "cocina", "habitacion", "sala"]
    largo_m: float = Field(gt=0.6, lt=14, description="metros")
    ancho_m: float = Field(gt=0.6, lt=14, description="metros")
    altura_m: float = Field(default=2.4, gt=1.8, lt=4.5)
    altura_enchape_m: Optional[float] = Field(default=None, gt=0.3, lt=4.5)
    incluye_ducha: Optional[bool] = None
    puertas: int = Field(default=1, ge=0, le=3)
    metros_lineales: Optional[float] = Field(default=None, gt=0, lt=20,
        description="mesón de cocina o closet corrido, cuando aplique")
    presupuesto_cop: int = Field(gt=0)

    @model_validator(mode="before")
    @classmethod
    def _aplicar_defaults_por_tipo(cls, data):
        if not isinstance(data, dict):
            return data
        tipo = data.get("tipo")
        for campo, valor in DEFAULTS_POR_TIPO.get(tipo, {}).items():
            data.setdefault(campo, valor)
        return data

    @field_validator("presupuesto_cop")
    @classmethod
    def _rango_presupuesto(cls, v: int) -> int:
        if v > PRESUPUESTO_MAX:
            raise ValueError("presupuesto fuera de rango")
        return v

    @model_validator(mode="after")
    def _coherencia(self) -> "Espacio":
        limites = LIMITES[self.tipo]
        if self.presupuesto_cop < limites["presupuesto_min"]:
            raise ValueError(
                f"presupuesto irreal para {self.tipo}: menos de "
                f"${limites['presupuesto_min']:,} no cubre ni lo mas economico")
        if self.largo_m > limites["lado_max"] or self.ancho_m > limites["lado_max"]:
            raise ValueError(f"medida fuera de rango para {self.tipo} "
                              f"(maximo {limites['lado_max']} m de lado)")
        if self.area_piso > limites["area_max"]:
            raise ValueError(f"area de {self.area_piso} m2 no corresponde a {self.tipo}")
        if self.altura_enchape_m is not None and self.altura_enchape_m > self.altura_m:
            raise ValueError("la altura de enchape no puede superar la altura del espacio")
        return self

    @property
    def area_piso(self) -> float:
        return round(self.largo_m * self.ancho_m, 2)

    @property
    def perimetro(self) -> float:
        return round(2 * (self.largo_m + self.ancho_m), 2)

    def variables(self) -> dict:
        """Variables disponibles para las formulas de reglas_obra.yaml. Solo se
        exponen las que este ambiente realmente usa: altura_enchape_m e
        incluye_ducha no significan nada en una sala, y aparecer con un valor
        por defecto haria que una formula de otro ambiente "aplicara" por
        accidente."""
        v = {
            "area_piso": self.area_piso,
            "perimetro": self.perimetro,
            "altura_m": self.altura_m,
            "puertas": float(self.puertas),
        }
        if self.altura_enchape_m is not None:
            v["altura_enchape_m"] = self.altura_enchape_m
        if self.incluye_ducha is not None:
            v["incluye_ducha"] = 1.0 if self.incluye_ducha else 0.0
        if self.metros_lineales is not None:
            v["metros_lineales"] = self.metros_lineales
        return v

    def sin_presupuesto(self) -> dict:
        """AISLAMIENTO DE INFORMACION: esto es lo unico que ve el Cuantificador.
        Si ve el presupuesto, va a ajustar las cantidades para que quepan."""
        d = self.model_dump()
        d.pop("presupuesto_cop", None)
        d["area_piso"] = self.area_piso
        d["perimetro"] = self.perimetro
        return d


class Requerimiento(BaseModel):
    """Cantidad de obra, SIN producto asignado. La produce el Cuantificador."""
    concepto: str
    cantidad: float = Field(gt=0)
    unidad: str
    formula: str
    fuente_regla: str
    regla_verificada: bool = False
    prioridad: int = Field(default=1, ge=1, le=3)
    regla_id: str = ""


class ItemCotizado(BaseModel):
    concepto: str
    requerimiento: Requerimiento
    producto: Producto
    unidades_a_comprar: int = Field(gt=0)
    subtotal_cop: int = Field(gt=0)
    justificacion: str = ""
    gama: str = "media"
    estado_precio: Literal["snapshot", "en_vivo", "cambio"] = "snapshot"
    precio_confirmado: Optional[int] = None


class Falla(BaseModel):
    codigo: str
    mensaje: str
    concepto: str = ""


class Cotizacion(BaseModel):
    espacio: Espacio
    items: list[ItemCotizado] = []
    faltantes: list[str] = []
    total_cop: int = 0
    holgura_cop: int = 0
    recortes: list[str] = []
    alternativas: list[str] = []
    fases: dict[str, list[str]] = {}
    cifras_sin_fuente: list[str] = []
    generada_en: str = Field(default_factory=ahora)
    aprobada_por_humano: bool = False

    def recalcular(self) -> "Cotizacion":
        self.total_cop = sum(i.subtotal_cop for i in self.items)
        self.holgura_cop = self.espacio.presupuesto_cop - self.total_cop
        self.cifras_sin_fuente = sorted({
            i.requerimiento.concepto for i in self.items if not i.requerimiento.regla_verificada
        })
        return self


def unidades_necesarias(req: Requerimiento, prod: Producto) -> int:
    """Puente entre cantidad de obra y unidad de venta. Homecenter vende cajas y
    bultos, no metros cuadrados ni kilos.

    NOTA: 'ml' (metros lineales, p.ej. meson o closet corrido) y 'Und' caen
    ambos al fallback final: se compra 1 unidad de venta por cada metro/unidad
    de obra, salvo que el producto declare su propio contenido por unidad. Si
    una regla de obra nueva necesita otro tipo de conversion (p.ej. metros
    lineales por modulo de mueble), hay que declararla aqui explicitamente:
    el fallback silencioso es exactamente el bug que tuvieron 'espejo' y
    'division de ducha' cuando su categoria no tenia filas."""
    contenido = None
    if req.unidad == "m2":
        contenido = prod.m2_por_caja
    elif req.unidad == "kg":
        contenido = prod.kg_por_bulto
    elif req.unidad == "galon":
        contenido = 1.0  # la cantidad ya viene en galones
    if contenido and contenido > 0:
        return max(1, ceil(req.cantidad / contenido))
    return max(1, ceil(req.cantidad))
