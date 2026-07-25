"""Memoria de sesion en SQLite. Permite el segundo turno ("y si le subo a 2.5M")
sin volver a cuantificar: el Supervisor lee lo que ya calculo."""
from __future__ import annotations
import json, sqlite3

DB = "datos/memoria.db"


def _con() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.execute("""CREATE TABLE IF NOT EXISTS memoria (
                   sesion TEXT, clave TEXT, valor TEXT, ts REAL DEFAULT (unixepoch()),
                   PRIMARY KEY (sesion, clave))""")
    return c


def escribir(sesion: str, clave: str, valor) -> None:
    with _con() as c:
        c.execute("INSERT OR REPLACE INTO memoria (sesion, clave, valor) VALUES (?,?,?)",
                  (sesion, clave, json.dumps(valor, ensure_ascii=False, default=str)))


def leer(sesion: str, clave: str):
    with _con() as c:
        r = c.execute("SELECT valor FROM memoria WHERE sesion=? AND clave=?",
                      (sesion, clave)).fetchone()
    return json.loads(r[0]) if r else None


def todo(sesion: str) -> dict:
    with _con() as c:
        rows = c.execute("SELECT clave, valor FROM memoria WHERE sesion=?", (sesion,)).fetchall()
    return {k: json.loads(v) for k, v in rows}


def olvidar(sesion: str) -> None:
    with _con() as c:
        c.execute("DELETE FROM memoria WHERE sesion=?", (sesion,))
