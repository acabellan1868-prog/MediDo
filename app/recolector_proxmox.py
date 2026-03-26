"""
MediDo — Recolector de metricas via Proxmox API.
Consulta host, VMs y almacenamiento del servidor Proxmox.
"""

import logging
import httpx

from app.config import PVE_HOST, PVE_NODE, PVE_TOKEN_ID, PVE_TOKEN_SECRET, PVE_VERIFY_SSL

logger = logging.getLogger("medido.proxmox")

# URL base de la API de Proxmox
_BASE_URL = f"https://{PVE_HOST}:8006/api2/json"


def _cabeceras() -> dict:
    """Devuelve las cabeceras de autenticacion para la API de Proxmox."""
    return {
        "Authorization": f"PVEAPIToken={PVE_TOKEN_ID}={PVE_TOKEN_SECRET}",
    }


def _consultar(endpoint: str) -> dict | None:
    """
    Hace GET a un endpoint de la API de Proxmox.
    Devuelve el contenido de 'data' o None si falla.
    """
    url = f"{_BASE_URL}/{endpoint}"
    try:
        respuesta = httpx.get(
            url,
            headers=_cabeceras(),
            verify=PVE_VERIFY_SSL,
            timeout=15.0,
        )
        respuesta.raise_for_status()
        return respuesta.json().get("data")
    except Exception as e:
        logger.error(f"Error consultando Proxmox {endpoint}: {e}")
        return None


def _bytes_a_gb(valor: int | float) -> float:
    """Convierte bytes a gigabytes redondeados a 1 decimal."""
    return round(valor / (1024 ** 3), 1)


def _porcentaje(usado, total) -> float:
    """Calcula porcentaje usado/total redondeado a 1 decimal."""
    if not total:
        return 0.0
    return round((usado / total) * 100, 1)


def obtener_estado_host() -> dict | None:
    """
    Obtiene metricas del host Proxmox (nodo).
    Endpoint: GET /nodes/{node}/status
    """
    datos = _consultar(f"nodes/{PVE_NODE}/status")
    if not datos:
        return None

    cpu = datos.get("cpu", 0)
    memoria = datos.get("memory", {})
    mem_total = memoria.get("total", 0)
    mem_usado = memoria.get("used", 0)
    uptime = datos.get("uptime", 0)

    return {
        "cpu_percent": round(cpu * 100, 1),
        "memoria": {
            "total_gb": _bytes_a_gb(mem_total),
            "usado_gb": _bytes_a_gb(mem_usado),
            "percent": _porcentaje(mem_usado, mem_total),
        },
        "uptime_dias": round(uptime / 86400, 1),
    }


def obtener_vms() -> list[dict]:
    """
    Obtiene la lista de VMs con sus metricas.
    Endpoint: GET /nodes/{node}/qemu
    """
    datos = _consultar(f"nodes/{PVE_NODE}/qemu")
    if not datos:
        return []

    vms = []
    for vm in datos:
        maxmem = vm.get("maxmem", 0)
        mem = vm.get("mem", 0)
        maxdisk = vm.get("maxdisk", 0)
        disk = vm.get("disk", 0)
        uptime = vm.get("uptime", 0)
        cpu = vm.get("cpu", 0)
        cpus = vm.get("cpus", 1)

        vms.append({
            "vmid": vm.get("vmid"),
            "nombre": vm.get("name", f"VM {vm.get('vmid')}"),
            "estado": vm.get("status", "desconocido"),
            "cpu_percent": round(cpu * 100, 1),
            "cpus": cpus,
            "memoria": {
                "total_gb": _bytes_a_gb(maxmem),
                "usado_gb": _bytes_a_gb(mem),
                "percent": _porcentaje(mem, maxmem),
            },
            "disco": {
                "total_gb": _bytes_a_gb(maxdisk),
                "usado_gb": _bytes_a_gb(disk),
                "percent": _porcentaje(disk, maxdisk),
            },
            "uptime_dias": round(uptime / 86400, 1),
        })

    return vms


def obtener_almacenamiento() -> list[dict]:
    """
    Obtiene informacion de almacenamiento del nodo.
    Endpoint: GET /nodes/{node}/storage
    """
    datos = _consultar(f"nodes/{PVE_NODE}/storage")
    if not datos:
        return []

    storages = []
    for s in datos:
        total = s.get("total", 0)
        usado = s.get("used", 0)
        storages.append({
            "nombre": s.get("storage", "desconocido"),
            "tipo": s.get("type", ""),
            "total_gb": _bytes_a_gb(total),
            "usado_gb": _bytes_a_gb(usado),
            "percent": _porcentaje(usado, total),
            "activo": bool(s.get("active", 0)),
            "contenido": s.get("content", ""),
        })

    return storages


def recolectar_proxmox() -> dict:
    """
    Recolecta todas las metricas de Proxmox: host, VMs y almacenamiento.
    Devuelve un dict completo y guarda snapshot en BD.
    """
    from app import bd

    host = obtener_estado_host()
    vms = obtener_vms()
    almacenamiento = obtener_almacenamiento()

    resultado = {
        "host": host,
        "vms": vms,
        "almacenamiento": almacenamiento,
    }

    # Guardar snapshot en BD (buscar VM 101 como referencia principal)
    if host:
        vm101 = next((vm for vm in vms if vm["vmid"] == 101), None)
        bd.ejecutar(
            """INSERT INTO metricas (
                pve_cpu_percent, pve_memoria_percent,
                pve_memoria_usado_gb, pve_memoria_total_gb, pve_uptime_dias,
                vm_cpu_percent, vm_memoria_percent,
                vm_memoria_usado_gb, vm_memoria_total_gb,
                vm_disco_percent, vm_disco_usado_gb, vm_disco_total_gb,
                vm_uptime_dias
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                host["cpu_percent"],
                host["memoria"]["percent"],
                host["memoria"]["usado_gb"],
                host["memoria"]["total_gb"],
                host["uptime_dias"],
                vm101["cpu_percent"] if vm101 else None,
                vm101["memoria"]["percent"] if vm101 else None,
                vm101["memoria"]["usado_gb"] if vm101 else None,
                vm101["memoria"]["total_gb"] if vm101 else None,
                vm101["disco"]["percent"] if vm101 else None,
                vm101["disco"]["usado_gb"] if vm101 else None,
                vm101["disco"]["total_gb"] if vm101 else None,
                vm101["uptime_dias"] if vm101 else None,
            ),
        )
        logger.info(
            f"Proxmox: CPU host {host['cpu_percent']}%, "
            f"RAM host {host['memoria']['percent']}%, "
            f"{len(vms)} VMs"
        )

    return resultado
