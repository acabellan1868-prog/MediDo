"""
MediDo — Health checker de servicios.
Comprueba periodicamente que cada servicio del ecosistema responde.
"""

import logging
import time
import httpx

from app.config import HA_TOKEN

logger = logging.getLogger("medido.health")

# Servicios a comprobar
# Nota: desde dentro del contenedor Docker (con extra_hosts):
#   - Contenedores Docker compose → por nombre (fido, hogar-api)
#   - Servicios en el host → host.docker.internal
#   - Servicios en otras IPs → IP directa
SERVICIOS = [
    {
        "nombre": "portal",
        "url": "http://host.docker.internal:80/",
        "esperado": [200],
    },
    {
        "nombre": "fido",
        "url": "http://fido:8080/api/resumen",
        "esperado": [200],
    },
    {
        "nombre": "redo",
        "url": "http://host.docker.internal:80/red/api/resumen",
        "esperado": [200],
    },
    {
        "nombre": "hogar-api",
        "url": "http://hogar-api:8080/lanzador",
        "esperado": [200],
    },
    {
        "nombre": "home-assistant",
        "url": "http://192.168.31.132:8123/api/",
        "esperado": [200, 401],
        "cabeceras": {},  # HA acepta 401 como "vivo" si no hay token
    },
    {
        "nombre": "kryptonite",
        "url": "http://host.docker.internal:5000/portafolio",
        "esperado": [200],
    },
    {
        "nombre": "nextcloud",
        "url": "http://host.docker.internal:8081/status.php",
        "esperado": [200, 400],  # 400 = nextcloud vivo pero rechaza HTTP plano
    },
    {
        "nombre": "portainer",
        "url": "https://host.docker.internal:9443/api/status",
        "esperado": [200],
    },
]


def comprobar_servicio(servicio: dict) -> dict:
    """
    Comprueba un servicio individual.
    Devuelve dict con: servicio, estado, tiempo_respuesta_ms, codigo_http, mensaje.
    """
    nombre = servicio["nombre"]
    url = servicio["url"]
    esperado = servicio["esperado"]

    # Cabeceras especiales (ej: HA con Bearer token)
    cabeceras = servicio.get("cabeceras", {})
    if nombre == "home-assistant" and HA_TOKEN:
        cabeceras["Authorization"] = f"Bearer {HA_TOKEN}"

    try:
        inicio = time.monotonic()
        respuesta = httpx.get(
            url,
            headers=cabeceras,
            timeout=10.0,
            verify=False,  # Portainer usa HTTPS autofirmado
            follow_redirects=True,
        )
        ms = int((time.monotonic() - inicio) * 1000)

        if respuesta.status_code in esperado:
            estado = "lento" if ms > 2000 else "ok"
            mensaje = None
        else:
            estado = "error"
            mensaje = f"HTTP {respuesta.status_code} (esperado {esperado})"

        return {
            "servicio": nombre,
            "estado": estado,
            "tiempo_respuesta_ms": ms,
            "codigo_http": respuesta.status_code,
            "mensaje": mensaje,
        }

    except httpx.TimeoutException:
        return {
            "servicio": nombre,
            "estado": "caido",
            "tiempo_respuesta_ms": 10000,
            "codigo_http": None,
            "mensaje": "Timeout (10s)",
        }
    except Exception as e:
        return {
            "servicio": nombre,
            "estado": "caido",
            "tiempo_respuesta_ms": None,
            "codigo_http": None,
            "mensaje": str(e)[:200],
        }


def ejecutar_health_checks() -> list[dict]:
    """
    Ejecuta health checks de todos los servicios.
    Guarda resultados en BD y devuelve la lista.
    """
    from app import bd

    resultados = []
    for servicio in SERVICIOS:
        resultado = comprobar_servicio(servicio)
        resultados.append(resultado)

        # Guardar en BD
        bd.ejecutar(
            """INSERT INTO health_checks (servicio, estado, tiempo_respuesta_ms,
               codigo_http, mensaje)
               VALUES (?, ?, ?, ?, ?)""",
            (
                resultado["servicio"],
                resultado["estado"],
                resultado["tiempo_respuesta_ms"],
                resultado["codigo_http"],
                resultado["mensaje"],
            ),
        )

    ok = sum(1 for r in resultados if r["estado"] == "ok")
    logger.info(f"Health checks: {ok}/{len(resultados)} OK")

    return resultados
