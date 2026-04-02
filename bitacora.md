# Bitácora — MediDo

## 2026-04-02

### Fase 5 — Tracking de Claude Code (Fase 13b de hogarOS)

Se inicia implementación de endpoints para recolectar datos de sesiones de Claude Code desde Windows.
El hook de Claude Code (verificado en Fase 13a) hace POST a estos endpoints.

**Arquitectura offline-first:**
```
Claude Code Hook (Windows)
  └─ POST /salud/api/claude/sesion (con tokens y coste)
     └─ MediDo guarda en tabla tracking_claude
        └─ GET /salud/api/claude/resumen (agregaciones para portal)
```

**Endpoints a implementar:**
- POST `/api/claude/sesion` — Recibe evento del hook, inserta en BD (idempotente)
- GET `/api/claude/resumen` — Agrega por período (día/semana/mes) con presupuesto

**Tabla tracking_claude:**
- Almacena: session_id, fecha_fin, directorio, proyecto, tokens (input/output/cache), costes USD
- UNIQUE en session_id → impide duplicados en reintentos del hook
- Índices en fecha_fin, session_id, proyecto para búsquedas rápidas

**Variables de entorno opcionales:**
- `CLAUDE_PRESUPUESTO_USD` — Presupuesto mensual (ej: 50.0)
- `CLAUDE_DIA_RESETEO` — Día del mes de reseteo (1-31, defecto: 1ro)

**Plan completo:** Ver `~/.claude/plans/fase-13b-medido.md`

---

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
