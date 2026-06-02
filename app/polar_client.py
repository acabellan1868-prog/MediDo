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
import xml.etree.ElementTree as ET
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


def _obtener_datos_ruta(cliente: httpx.Client, ejercicio_id: str) -> dict:
    """
    Descarga el TCX del ejercicio y extrae velocidad máxima y desnivel.
    Devuelve dict con velocidad_maxima_kmh, desnivel_positivo, desnivel_negativo.
    Devuelve valores None si no hay ruta o falla la descarga.
    """
    resultado = {"velocidad_maxima_kmh": None, "desnivel_positivo": None, "desnivel_negativo": None}
    try:
        resp = cliente.get(
            f"{BASE_URL}/exercises/{ejercicio_id}/tcx",
            headers={**_cabeceras(), "Accept": "application/vnd.garmin.tcx+xml"},
            timeout=30,
        )
        if resp.status_code != 200:
            return resultado

        # Parsear XML — namespace del TCX de Garmin
        ns = {"tcx": "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"}
        raiz = ET.fromstring(resp.text)

        # Velocidad máxima: tomar el máximo entre todos los laps
        vel_max_ms = 0.0
        for lap in raiz.findall(".//tcx:Lap", ns):
            vel = lap.findtext("tcx:MaximumSpeed", namespaces=ns)
            if vel:
                vel_max_ms = max(vel_max_ms, float(vel))

        if vel_max_ms > 0:
            resultado["velocidad_maxima_kmh"] = round(vel_max_ms * 3.6, 1)

        # Desnivel: procesar todas las altitudes con umbral de 5m para filtrar ruido GPS
        altitudes = []
        for tp in raiz.findall(".//tcx:Trackpoint", ns):
            alt = tp.findtext("tcx:AltitudeMeters", namespaces=ns)
            if alt:
                altitudes.append(float(alt))

        if len(altitudes) > 1:
            ganancia = 0.0
            perdida = 0.0
            UMBRAL = 5.0  # metros — filtra ruido GPS
            acum = 0.0
            for i in range(1, len(altitudes)):
                acum += altitudes[i] - altitudes[i - 1]
                if acum >= UMBRAL:
                    ganancia += acum
                    acum = 0.0
                elif acum <= -UMBRAL:
                    perdida += abs(acum)
                    acum = 0.0
            resultado["desnivel_positivo"] = int(round(ganancia))
            resultado["desnivel_negativo"] = int(round(perdida))

    except Exception as e:
        logger.warning(f"Polar: no se pudieron obtener datos de ruta para {ejercicio_id}: {e}")

    return resultado


def sincronizar_ejercicios() -> list[dict]:
    """
    Descarga todos los ejercicios disponibles desde Polar Flow usando el endpoint
    no transaccional GET /v3/exercises. No consume los datos, por lo que es seguro
    llamarlo repetidamente. La deduplicación se hace por polar_id en la BD.
    Devuelve lista de dicts listos para insertar en la BD.
    """
    if not POLAR_ACCESS_TOKEN:
        logger.warning("Polar no configurado (POLAR_ACCESS_TOKEN vacío)")
        return []

    try:
        with httpx.Client(timeout=30) as cliente:
            resp = cliente.get(
                f"{BASE_URL}/exercises",
                headers=_cabeceras(),
            )
            if resp.status_code == 204 or resp.text.strip() in ("", "[]"):
                logger.info("Polar: no hay ejercicios disponibles")
                return []
            if resp.status_code != 200:
                logger.error(f"Polar: error obteniendo ejercicios ({resp.status_code}): {resp.text}")
                return []

            datos_lista = resp.json()
            if not datos_lista:
                logger.info("Polar: lista de ejercicios vacía")
                return []

            ejercicios = []
            for datos in datos_lista:
                ejercicio = _parsear_ejercicio(datos)
                if not ejercicio:
                    continue
                # Velocidad media: calculada gratis de distancia/duración
                if ejercicio.get("distancia_km") and ejercicio["duracion_segundos"] > 0:
                    ejercicio["velocidad_media_kmh"] = round(
                        ejercicio["distancia_km"] / (ejercicio["duracion_segundos"] / 3600), 1
                    )
                else:
                    ejercicio["velocidad_media_kmh"] = None
                # tiene_ruta indica si hay GPS disponible (para mostrar el botón en el frontend)
                ejercicio["tiene_ruta"] = bool(datos.get("has_route"))
                # Velocidad máxima y desnivel NO se descargan aquí — son bajo demanda via TCX
                ejercicio["velocidad_maxima_kmh"] = None
                ejercicio["desnivel_positivo"] = None
                ejercicio["desnivel_negativo"] = None
                ejercicios.append(ejercicio)

            logger.info(f"Polar: {len(ejercicios)} ejercicio(s) disponibles en la API")
            return ejercicios

    except httpx.RequestError as e:
        logger.error(f"Polar: error de red al sincronizar: {e}")
        return []
    except Exception as e:
        logger.error(f"Polar: error inesperado al sincronizar: {e}")
        return []


def _parsear_ejercicio(datos: dict) -> dict | None:
    """
    Convierte el JSON de un ejercicio Polar al formato de nuestra BD.
    Compatible con el endpoint GET /v3/exercises (campos sin guión).
    Devuelve None si faltan campos obligatorios.
    """
    polar_id = str(datos.get("id", ""))
    if not polar_id:
        return None

    # El endpoint /v3/exercises usa start_time (guión bajo)
    fecha_inicio = datos.get("start_time") or datos.get("start-time", "")
    if not fecha_inicio:
        return None

    duracion_iso = datos.get("duration", "")
    duracion_seg = _parsear_duracion_iso(duracion_iso)
    if duracion_seg == 0:
        return None

    tipo = datos.get("sport", "UNKNOWN").upper()
    # detailed_sport_info es más específico (CYCLING, STRETCHING, RUNNING...)
    detalle = datos.get("detailed_sport_info") or datos.get("detailed-sport-info", "")
    if detalle:
        tipo = detalle.upper()

    distancia_m = datos.get("distance")
    distancia_km = round(distancia_m / 1000, 2) if distancia_m else None

    calorias = datos.get("calories")

    # El endpoint /v3/exercises usa heart_rate (guión bajo)
    fc_datos = datos.get("heart_rate") or datos.get("heart-rate") or {}
    fc_promedio = fc_datos.get("average") if fc_datos else None
    fc_maxima = fc_datos.get("maximum") if fc_datos else None

    fecha_subida = datos.get("upload_time") or datos.get("upload-time")

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
