# Bitácora — MediDo

## 2026-03-27

### Despliegue inicial

Primera versión desplegada en VM 101. Proyecto creado desde cero siguiendo
el patrón de ReDo y FiDo.

Funcionalidades de la v1:
- Recolector de métricas Proxmox (CPU, RAM, disco, estado de VMs)
- Recolector de estado de contenedores Docker
- Health checks HTTP para 8 servicios del ecosistema
- Alertador con umbrales configurables + notificaciones ntfy
- Dashboard web: Resumen / Proxmox / Contenedores / Servicios / Alertas
- API REST completa

### Corrección de health checks — servicios con falsos positivos

Tres servicios generaban alertas incorrectas aunque estaban operativos:

- **portainer**: URL incorrecta `https://host.docker.internal:9443`. Corregido
  a `http://host.docker.internal:9000/api/status` (HTTP, puerto 9000).
- **nextcloud**: `/status.php` devuelve HTTP 400 para peticiones no autenticadas
  (comportamiento esperado de Nextcloud). Corregido a aceptar HTTP 400 como válido.
- **redo**: endpoint `/api/estado` no existe en ReDo. Corregido a `/api/resumen`.
  URL corregida a `host.docker.internal:8083` (la IP LAN falla, ver analisis.md).
