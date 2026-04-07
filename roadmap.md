# Roadmap — MediDo

## Estado actual

**Fecha:** 2026-04-04

**Status:** Fase 5d en producción. Mejoras menores de UI: tab renombrado a CLAUDE, bug de colapso de sesiones corregido.
**Próximo:** Pendiente de nuevas funcionalidades o bugs reportados.

---

## Fases

### Fase 1 — Backend + API ✅

- [x] Estructura del proyecto (patron de ReDo/FiDo)
- [x] Configuracion centralizada (`config.py` con variables de entorno)
- [x] Base de datos SQLite (metricas, health_checks, alertas)
- [x] Recolector Proxmox API (host, VMs, almacenamiento)
- [x] Recolector Docker SDK (contenedores, estado, uptime)
- [x] Health checker HTTP (8 servicios: portal, fido, redo, hogar-api, HA, kryptonite, nextcloud, portainer)
- [x] Alertador con umbrales (CPU, RAM, disco) + NTFY
- [x] Limpieza nocturna de historial (90 dias)
- [x] API REST completa:
  - `GET /api/resumen` — estado global para tarjeta del portal
  - `GET /api/proxmox` — metricas actuales (host + VMs + storage)
  - `GET /api/proxmox/historial?horas=24` — serie temporal
  - `GET /api/contenedores` — lista de contenedores Docker
  - `GET /api/servicios` — ultimo health check de cada servicio
  - `GET /api/servicios/{nombre}/historial` — historial de un servicio
  - `GET /api/alertas` — alertas activas y recientes
  - `POST /api/alertas/{id}/resolver` — marcar alerta como resuelta

### Fase 2 — Frontend SPA ✅

- [x] Frontend vanilla HTML/CSS/JS con hogar.css
- [x] Tabs de navegacion: General, Proxmox, Contenedores, Servicios, Historial, Alertas
- [x] Semaforo global (ok/warning/danger)
- [x] Tarjetas de metricas con barras de progreso y colores semanticos
- [x] Detalle Proxmox: host, VMs con CPU/RAM/disco, almacenamiento
- [x] Grid de contenedores con estado y uptime
- [x] Grid de servicios con latencia
- [x] Grafica de historial 24h (canvas 2D, 4 series)
- [x] Feed de alertas con boton "Resolver"
- [x] Refresco automatico cada 60 segundos

### Fase 3 — Integracion hogarOS ✅

- [x] Dockerfile (python:3.12-slim, puerto 8084)
- [x] Servicio `medido` en docker-compose.yml (socket Docker :ro, extra_hosts)
- [x] Upstream y location `/salud/` en nginx.conf (con sub_filter)
- [x] Location `/salud/static/` para hogar.css compartido
- [x] Enlace "Salud" en drawer del portal
- [x] Variables Proxmox en .env y .env.example
- [x] medido-build en actualizar.sh
- [x] Repo GitHub: acabellan1868-prog/MediDo
- [x] Clonado en /mnt/datos/medido-build/, datos en /mnt/datos/medido/

### Fase 4 — Estandarizacion UI ✅

- [x] Header con lumina + barra + marca (patron ecosistema)
- [x] Hamburguesa a la derecha (igual que portal, ReDo, FiDo)
- [x] Drawer con overlay y boton cerrar
- [x] Enlaces con window.location.origin (evita sub_filter)
- [x] Orden estandar del drawer: app activa → otras apps → portal → tema
- [x] Actualizado drawer de ReDo (añadido enlace a Salud, portal al final)
- [x] Actualizado drawer de FiDo (añadidos enlaces a Red y Salud, portal al final)

### Fase 5 — Tracking de Claude Code ✅

Recolecta datos de uso de Claude Code desde Windows (tokens, coste estimado).
El hook de Claude Code (Fase 13a) POST a estos endpoints.

- [x] 🤖 Tabla `tracking_claude` en esquema.sql
- [x] 🤖 Variables de entorno: `CLAUDE_PRESUPUESTO_EUR`, `CLAUDE_DIA_RESETEO`, `CLAUDE_LIMITE_5H_TOKENS`, `CLAUDE_LIMITE_SEMANA_TOKENS`
- [x] 🤖 Router `/api/claude` con:
  - [x] POST `/api/claude/sesion` — recibe eventos del hook (idempotente)
  - [x] GET `/api/claude/resumen` — agrega por período (día/semana/mes) con presupuesto y limites
- [x] 👤 Tarjeta en portal mostrando: sesiones, tokens, coste, presupuesto, limites 5h/semana

### Fase 5d — Desglose de respuestas por sesión ✅

Una fila por sesión con opción de expandir para ver cada respuesta individual.

- [x] 🤖 Quitar `UNIQUE` de `session_id` en `esquema.sql`
- [x] 🤖 `migrar_bd()` en `bd.py` — migración automática de BD existente en producción
- [x] 🤖 `POST /sesion` inserta siempre (sin UNIQUE, sin dedup)
- [x] 🤖 `GET /sesiones` agrupa por `session_id` con `MAX()` + `num_respuestas`
- [x] 🤖 `GET /sesiones/{session_id}` — detalle de respuestas individuales
- [x] 🤖 Frontend: columna `#`, botón chevron expandible, mini-tabla de respuestas

---

### Fase 5c — Borrado de sesiones en MediDo ✅

Gestión básica de sesiones para limpiar datos durante el período de pruebas.

- [x] 🤖 Endpoint `DELETE /api/claude/sesiones/{session_id}`
- [x] 🤖 Botón de borrado por fila en la tabla de sesiones (con confirmación)

---

### Fase 5b — Pestaña CLAUDE Code en MediDo ✅

Tabla detallada de sesiones individuales con filtros por período y proyecto.
Permite detectar sesiones que se "fueron de madre" en gastos o tokens.

- [x] 🤖 Endpoint `GET /api/claude/sesiones` con query params: `periodo`, `proyecto`, `limite`
  - Devuelve: sesiones, totales (count, tokens, coste), lista de proyectos únicos
- [x] 🤖 Nueva pestaña "Claude Code" en `static/index.html`
  - Filtros: período (Hoy/Esta semana/Este mes), proyecto (dropdown dinámico)
  - Tabla: Fecha/Hora | Proyecto | Input Tok | Output Tok | Cache Tok | Coste USD
  - Sumas: Sesiones | Tokens Total | Coste Total USD
- [x] 🤖 Funciones JavaScript: `cargarSesionesClaudeAPI()`, `cargarProyectosClaude()`
- [x] 🤖 Fix bug tokens a 0 en `claude-tracker.py` (`message.usage` en vez de `usage`)
- [x] 👤 Desplegar en VM 101 y verificar

---

## Pendiente / Mejoras futuras

### Fase 6 — Tarjeta en el portal ✅

- [x] Tarjeta "Salud del sistema" en el grid bento del portal
- [x] Consume `/salud/api/resumen`
- [x] Muestra semaforo + CPU/RAM/disco + contenedores + servicios

### Fase 7 — Mejoras de metricas

- [ ] Disco real de las VMs (via QEMU guest agent)
- [ ] Deteccion de disco USB externo en almacenamiento
- [ ] Metricas por contenedor (CPU%, memoria) — actualmente desactivado por rendimiento
- [ ] Estado de backups (consultar hogar-api /api/backup)

### Fase 8 — Mejoras de UI

- [ ] Responsive completo (probar en movil)
- [ ] Graficas mas detalladas (zoom, tooltip, multiples periodos)
- [ ] Detalle de cada VM al hacer clic
- [ ] Historial de health checks por servicio (grafica de latencia)

### Fase 9 — Configuracion

- [ ] Pantalla de settings en MediDo (umbrales, intervalos, servicios a monitorizar)
- [ ] Gestion de contenedores ignorados desde la UI

---

## Decisiones tecnicas

| Fecha | Decision | Motivo |
|---|---|---|
| 2026-03-26 | Proxmox API en vez de psutil | psutil dentro de un contenedor ve el contenedor, no el host. Proxmox ve todo desde arriba |
| 2026-03-26 | No recoger stats por contenedor | `container.stats()` tarda ~1s/contenedor. Con 16 contenedores bloquea demasiado |
| 2026-03-26 | Mismo topic NTFY que ReDo | Un solo canal de notificaciones para todo el ecosistema |
| 2026-03-27 | window.location.origin en drawers | Evita que sub_filter de Nginx reescriba las rutas de navegacion |

---

## Datos de configuracion

| Dato | Valor |
|---|---|
| Puerto | 8084 |
| Proxy Nginx | /salud/ |
| Proxmox IP | 192.168.31.103 |
| Nodo Proxmox | deeloco |
| Token API | root@pam!medido |
| NTFY topic | hogaros-3ca6f61b |
| Intervalo metricas | 300s (5 min) |
| Intervalo health checks | 60s |
| Retencion historial | 90 dias |
