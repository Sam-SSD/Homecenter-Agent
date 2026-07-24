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

    def contenido_por_unidad(self) -> Optional[float]:
        return self.m2_por_caja or self.kg_por_bulto or self.rendimiento_m2


class Espacio(BaseModel):
    """GUARDRAIL: rechaza medidas y presupuestos incoherentes."""
    tipo: Literal["bano"] = "bano"
    largo_m: float = Field(gt=0.6, lt=8, description="metros")
    ancho_m: float = Field(gt=0.6, lt=8, description="metros")
    altura_m: float = Field(default=2.4, gt=1.8, lt=4.5)
    altura_enchape_m: float = Field(default=2.0, gt=0.3, lt=4.5)
    incluye_ducha: bool = True
    puertas: int = Field(default=1, ge=0, le=3)
    presupuesto_cop: int = Field(gt=0)

    @field_validator("presupuesto_cop")
    @classmethod
    def _rango_presupuesto(cls, v: int) -> int:
        if v < 500_000:
            raise ValueError("presupuesto irreal: menos de $500.000 no cubre ni el sanitario mas economico")
        if v > 200_000_000:
            raise ValueError("presupuesto fuera de rango para un bano")
        return v

    @model_validator(mode="after")
    def _coherencia(self) -> "Espacio":
        if self.area_piso > 25:
            raise ValueError(f"area de {self.area_piso} m2 no corresponde a un bano")
        if self.altura_enchape_m > self.altura_m:
            raise ValueError("la altura de enchape no puede superar la altura del bano")
        return self

    @property
    def area_piso(self) -> float:
        return round(self.largo_m * self.ancho_m, 2)

    @property
    def perimetro(self) -> float:
        return round(2 * (self.largo_m + self.ancho_m), 2)

    def variables(self) -> dict:
        """Variables disponibles para las formulas de reglas_obra.yaml."""
        return {
            "area_piso": self.area_piso,
            "perimetro": self.perimetro,
            "altura_m": self.altura_m,
            "altura_enchape_m": self.altura_enchape_m,
            "puertas": float(self.puertas),
            "incluye_ducha": 1.0 if self.incluye_ducha else 0.0,
        }

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
    bultos, no metros cuadrados ni kilos."""
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
