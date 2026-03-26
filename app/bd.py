"""
MediDo — Modulo de base de datos SQLite.
Gestion de conexion, helpers e inicializacion del esquema.
"""

import sqlite3
from pathlib import Path

from app.config import RUTA_BD


def obtener_conexion() -> sqlite3.Connection:
    """Abre una conexion a la BD con WAL y foreign keys activados."""
    conexion = sqlite3.connect(RUTA_BD)
    conexion.row_factory = sqlite3.Row
    conexion.execute("PRAGMA journal_mode=WAL")
    conexion.execute("PRAGMA foreign_keys=ON")
    return conexion


def inicializar_bd():
    """Crea las tablas si no existen ejecutando esquema.sql."""
    ruta_esquema = Path(__file__).parent / "esquema.sql"
    conexion = obtener_conexion()
    conexion.executescript(ruta_esquema.read_text(encoding="utf-8"))
    conexion.close()


def consultar_todos(sql: str, parametros: tuple = ()) -> list[dict]:
    """Ejecuta una consulta SELECT y devuelve todas las filas como lista de dicts."""
    conexion = obtener_conexion()
    filas = conexion.execute(sql, parametros).fetchall()
    conexion.close()
    return [dict(fila) for fila in filas]


def consultar_uno(sql: str, parametros: tuple = ()) -> dict | None:
    """Ejecuta una consulta SELECT y devuelve una fila como dict, o None."""
    conexion = obtener_conexion()
    fila = conexion.execute(sql, parametros).fetchone()
    conexion.close()
    return dict(fila) if fila else None


def ejecutar(sql: str, parametros: tuple = ()) -> int:
    """Ejecuta INSERT/UPDATE/DELETE y devuelve el lastrowid."""
    conexion = obtener_conexion()
    cursor = conexion.execute(sql, parametros)
    conexion.commit()
    ultimo_id = cursor.lastrowid
    conexion.close()
    return ultimo_id


def ejecutar_varios(sql: str, lista_parametros: list[tuple]) -> None:
    """Ejecuta la misma sentencia con multiples conjuntos de parametros."""
    conexion = obtener_conexion()
    conexion.executemany(sql, lista_parametros)
    conexion.commit()
    conexion.close()
