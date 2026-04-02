# Bitácora — MediDo

## 2026-04-03

### Fase 5b — Pestaña "CLAUDE Code" en MediDo

Se implementa pestaña con historial detallado de sesiones individuales de Claude Code,
permitiendo filtrar por período y proyecto para detectar sesiones con alto gasto.

**Cambios:**
- `app/rutas/claude.py`: Nuevo endpoint `GET /api/claude/sesiones`
  - Query params: `periodo` (dia|semana|mes), `proyecto` (opcional), `limite` (defecto 1000)
  - Devuelve: sesiones individuales, totales agregados (count, tokens, coste), lista de proyectos únicos
  - Lógica de rango de fechas reutilizada de `resumen()`

- `static/index.html`: Nueva pestaña y panel
  - Botón "Claude Code" después de Alertas en menú de tabs
  - Panel con filtros (período + proyecto dinámico) y tabla de sesiones
  - Tabla: Fecha/Hora | Proyecto | Input Tok | Output Tok | Cache Tok | Coste USD
  - Sumas: Sesiones | Tokens Total | Coste Total USD
  - Funciones JavaScript: `cargarSesionesClaudeAPI()`, `cargarProyectosClaude()`
  - Integrado en `cambiarTab('claude')` y refresco automático (60s)

**Arquitectura:**
- Endpoint calcula proyectos únicos para llenar dropdown dinámico
- Tabla renderizada con `map()` → `join('')` (patrón ReDo)
- Sumas recalculadas en cada carga (sin caché local)

---

## 2026-04-02

### Fase 13d — Limites de tokens en Claude tracking

Se agrega soporte para limites de tokens en ventanas móviles (rolling windows).

**Cambios:**
- `config.py`: Variables `CLAUDE_LIMITE_5H_TOKENS` (200k) y `CLAUDE_LIMITE_SEMANA_TOKENS` (4M)
- `rutas/claude.py`: Queries para sumar tokens en últimas 5h y últimas 7 días
- API `/claude/resumen` devuelve nueva sección `limites_tokens` con porcentajes
- `hogarOS/portal`: Tarjeta muestra 2 barras de progreso para limites (warning >=75%, danger >=90%)

**Arquitectura:** Ventanas móviles basadas en `datetime(fecha_fin)`, sin reseteo manual.

**Commits:**
- MediDo: `13d6cb1`
- hogarOS: `515b058`

---

### Fase 13c — Tarjeta "Asistente IA" en portal

Se implementa tarjeta en dashboard mostrando datos de Claude Code (sesiones, tokens, coste, presupuesto).

---

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
