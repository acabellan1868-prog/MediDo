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


def migrar_bd():
    """Aplica migraciones de esquema sobre una BD ya existente.

    Migración 1: eliminar UNIQUE de session_id en tracking_claude para permitir
    múltiples entradas por sesión (una por respuesta de Claude Code).
    """
    conexion = obtener_conexion()
    fila = conexion.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='tracking_claude'"
    ).fetchone()
    if fila and "UNIQUE" in fila[0]:
        conexion.executescript("""
            CREATE TABLE tracking_claude_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                fecha_fin TEXT NOT NULL,
                directorio TEXT,
                proyecto TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens INTEGER NOT NULL DEFAULT 0,
                cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
                coste_input_usd REAL NOT NULL DEFAULT 0.0,
                coste_output_usd REAL NOT NULL DEFAULT 0.0,
                coste_cache_usd REAL NOT NULL DEFAULT 0.0,
                fecha_registro TEXT NOT NULL DEFAULT (datetime('now')),
                sincronizado INTEGER NOT NULL DEFAULT 0,
                CHECK(input_tokens >= 0),
                CHECK(output_tokens >= 0),
                CHECK(cache_read_tokens >= 0),
                CHECK(cache_creation_tokens >= 0),
                CHECK(coste_input_usd >= 0),
                CHECK(coste_output_usd >= 0),
                CHECK(coste_cache_usd >= 0)
            );
            INSERT INTO tracking_claude_new SELECT * FROM tracking_claude;
            DROP TABLE tracking_claude;
            ALTER TABLE tracking_claude_new RENAME TO tracking_claude;
        """)
    conexion.close()


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
