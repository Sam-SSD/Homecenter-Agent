"""Observabilidad. Cada paso del loop queda registrado: es la evidencia del
componente de auto-correccion y lo que se muestra en pantalla durante la demo."""
from __future__ import annotations
import json, pathlib, time, uuid


class Traza:
    def __init__(self, etiqueta: str = "corrida"):
        self.id = f"{etiqueta}-{uuid.uuid4().hex[:8]}"
        self.t0 = time.time()
        self.pasos: list[dict] = []

    def paso(self, actor: str, tipo: str, detalle: str = "", **extra) -> dict:
        p = {"i": len(self.pasos), "t": round(time.time() - self.t0, 2),
             "actor": actor, "tipo": tipo, "detalle": detalle, **extra}
        self.pasos.append(p)
        print(f"  [{p['t']:6.2f}s] {actor:14} {tipo:20} {detalle[:90]}")
        return p

    def herramientas_usadas(self) -> list[str]:
        return [p["detalle"] for p in self.pasos if p["tipo"] == "tool_use"]

    def hubo_autocorreccion(self) -> bool:
        return any(p["tipo"] == "rechazo" for p in self.pasos)

    def guardar(self, carpeta: str = "trazas") -> str:
        pathlib.Path(carpeta).mkdir(exist_ok=True)
        ruta = f"{carpeta}/{self.id}.json"
        json.dump({"id": self.id, "pasos": self.pasos},
                  open(ruta, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return ruta

    def resumen(self) -> dict:
        return {
            "id": self.id,
            "pasos": len(self.pasos),
            "segundos": round(time.time() - self.t0, 2),
            "herramientas": self.herramientas_usadas(),
            "autocorreccion": self.hubo_autocorreccion(),
        }
