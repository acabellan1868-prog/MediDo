"""
MediDo — Cliente de la API Polar AccessLink v3.
Sincroniza ejercicios nuevos desde Polar Flow usando el modelo de transacciones:
  1. Crear transacción → obtener ID
  2. Descargar lista de ejercicios de la transacción
  3. Descargar detalle de cada ejercicio
  4. Confirmar (commit) la transacción
Los ejercicios ya vistos no vuelven a aparecer en futuras transacciones.
"""

import re
import logging
import httpx

from app.config import POLAR_ACCESS_TOKEN, POLAR_USER_ID

logger = logging.getLogger("medido.polar")

BASE_URL = "https://www.polaraccesslink.com/v3"


def _cabeceras() -> dict:
    """Cabeceras comunes para todas las peticiones a Polar."""
    return {
        "Authorization": f"Bearer {POLAR_ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _parsear_duracion_iso(duracion: str) -> int:
    """
    Convierte una duración ISO 8601 (PT1H30M15S) a segundos enteros.
    Ejemplos: PT45M → 2700, PT1H → 3600, PT1H30M → 5400
    """
    if not duracion:
        return 0
    patron = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?", duracion)
    if not patron:
        return 0
    horas = int(patron.group(1) or 0)
    minutos = int(patron.group(2) or 0)
    segundos = float(patron.group(3) or 0)
    return int(horas * 3600 + minutos * 60 + segundos)


def sincronizar_ejercicios() -> list[dict]:
    """
    Descarga los ejercicios nuevos desde Polar Flow.
    Devuelve lista de dicts listos para insertar en la BD.
    Devuelve lista vacía si no hay ejercicios nuevos o si Polar no está configurado.
    """
    if not POLAR_ACCESS_TOKEN or not POLAR_USER_ID:
        logger.warning("Polar no configurado (POLAR_ACCESS_TOKEN o POLAR_USER_ID vacíos)")
        return []

    url_base = f"{BASE_URL}/users/{POLAR_USER_ID}"

    try:
        with httpx.Client(timeout=30) as cliente:

            # --- Paso 1: Crear transacción ---
            resp = cliente.post(
                f"{url_base}/exercise-transactions",
                headers=_cabeceras(),
            )
            if resp.status_code == 204:
                logger.info("Polar: no hay ejercicios nuevos")
                return []
            if resp.status_code != 201:
                logger.error(f"Polar: error creando transacción ({resp.status_code}): {resp.text}")
                return []

            transaccion = resp.json()
            transaction_id = transaccion.get("transaction-id")
            if not transaction_id:
                logger.error("Polar: respuesta de transacción sin transaction-id")
                return []

            logger.info(f"Polar: transacción creada (id={transaction_id})")

            # --- Paso 2: Listar ejercicios de la transacción ---
            resp = cliente.get(
                f"{url_base}/exercise-transactions/{transaction_id}",
                headers=_cabeceras(),
            )
            if resp.status_code != 200:
                logger.error(f"Polar: error listando ejercicios ({resp.status_code})")
                return []

            lista = resp.json()
            enlaces = lista.get("exercises", [])
            if not enlaces:
                logger.info("Polar: transacción sin ejercicios")
                _confirmar_transaccion(cliente, url_base, transaction_id)
                return []

            logger.info(f"Polar: {len(enlaces)} ejercicio(s) en la transacción")

            # --- Paso 3: Descargar detalle de cada ejercicio ---
            ejercicios = []
            for enlace in enlaces:
                url_ejercicio = enlace.get("url", "")
                if not url_ejercicio:
                    continue
                resp_ej = cliente.get(url_ejercicio, headers=_cabeceras())
                if resp_ej.status_code != 200:
                    logger.warning(f"Polar: no se pudo obtener ejercicio {url_ejercicio} ({resp_ej.status_code})")
                    continue
                datos = resp_ej.json()
                ejercicio = _parsear_ejercicio(datos)
                if ejercicio:
                    ejercicios.append(ejercicio)

            # --- Paso 4: Confirmar transacción ---
            _confirmar_transaccion(cliente, url_base, transaction_id)

            logger.info(f"Polar: {len(ejercicios)} ejercicio(s) procesados")
            return ejercicios

    except httpx.RequestError as e:
        logger.error(f"Polar: error de red al sincronizar: {e}")
        return []
    except Exception as e:
        logger.error(f"Polar: error inesperado al sincronizar: {e}")
        return []


def _confirmar_transaccion(cliente: httpx.Client, url_base: str, transaction_id: int) -> None:
    """Confirma (commit) una transacción de ejercicios en Polar."""
    resp = cliente.put(
        f"{url_base}/exercise-transactions/{transaction_id}",
        headers=_cabeceras(),
    )
    if resp.status_code == 200:
        logger.info(f"Polar: transacción {transaction_id} confirmada")
    else:
        logger.warning(f"Polar: error confirmando transacción {transaction_id} ({resp.status_code})")


def _parsear_ejercicio(datos: dict) -> dict | None:
    """
    Convierte el JSON de un ejercicio Polar al formato de nuestra BD.
    Devuelve None si faltan campos obligatorios.
    """
    polar_id = str(datos.get("id", ""))
    if not polar_id:
        return None

    fecha_inicio = datos.get("start-time", "")
    if not fecha_inicio:
        return None

    duracion_iso = datos.get("duration", "")
    duracion_seg = _parsear_duracion_iso(duracion_iso)
    if duracion_seg == 0:
        return None

    tipo = datos.get("sport", "UNKNOWN").upper()
    # Usar detailed-sport-info si está disponible y es más específico
    detalle = datos.get("detailed-sport-info", "")
    if detalle:
        tipo = detalle.upper()

    distancia_m = datos.get("distance")
    distancia_km = round(distancia_m / 1000, 2) if distancia_m else None

    calorias = datos.get("calories")

    fc_datos = datos.get("heart-rate", {})
    fc_promedio = fc_datos.get("average") if fc_datos else None
    fc_maxima = fc_datos.get("maximum") if fc_datos else None

    fecha_subida = datos.get("upload-time")

    return {
        "polar_id": polar_id,
        "fecha_inicio": fecha_inicio,
        "fecha_subida": fecha_subida,
        "tipo": tipo,
        "distancia_km": distancia_km,
        "duracion_segundos": duracion_seg,
        "calorias": calorias,
        "fc_promedio": fc_promedio,
        "fc_maxima": fc_maxima,
    }
