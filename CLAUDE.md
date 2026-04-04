# CLAUDE.md — MediDo

## Qué es
Monitor de métricas y salud del hogar. Recolecta métricas de Proxmox, estado de contenedores Docker, health checks de servicios y genera alertas vía NTFY.

- **Repo:** acabellan1868-prog/MediDo
- **Local:** `Desarrollo/MediDo/`
- **Servidor:** `/mnt/datos/medido-build/` (build context), `/mnt/datos/medido/medido.db` (datos)
- **Proxy:** `/salud/` → `medido:8084`

## Estructura

```
MediDo/
├── app/
│   ├── principal.py             ← FastAPI + APScheduler
│   ├── bd.py
│   ├── config.py
│   ├── esquema.sql
│   ├── recolector_proxmox.py
│   ├── recolector_docker.py
│   ├── health_checker.py
│   ├── alertador.py
│   └── rutas/
│       ├── resumen.py
│       ├── proxmox.py
│       ├── contenedores.py
│       ├── servicios.py
│       ├── alertas.py
│       └── claude.py            ← endpoints monitor de uso Claude Code
├── static/
│   └── index.html               ← SPA con tabs: General, Proxmox, Contenedores, Servicios, Historial, Alertas, Claude
└── Dockerfile
```

## Health checks — URLs y gotchas

| Servicio | URL | Notas |
|----------|-----|-------|
| portal | `http://host.docker.internal:80/` | |
| fido | `http://fido:8080/api/resumen` | nombre de contenedor, red bridge |
| redo | `http://host.docker.internal:8083/api/resumen` | network_mode:host → NO usar IP LAN |
| hogar-api | `http://hogar-api:8080/lanzador` | nombre de contenedor |
| home-assistant | `http://192.168.31.132:8123/api/` | acepta 200 y 401 |
| kryptonite | `http://host.docker.internal:5000/portafolio` | |
| nextcloud | `http://host.docker.internal:8081/status.php` | acepta 200 y 400 |
| portainer | `http://192.168.31.131:9000/api/status` | HTTP puerto 9000, no HTTPS 9443 |

**Por qué redo usa host.docker.internal:** `network_mode:host` no crea reglas iptables, así que el tráfico desde red bridge a `192.168.31.131:8083` es rechazado. `host.docker.internal` resuelve al gateway del bridge (alcanzable).

## API

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/resumen` | Estado global (tarjeta portal) |
| GET | `/api/proxmox` | Métricas actuales Proxmox |
| GET | `/api/proxmox/historial?horas=24` | Serie temporal |
| GET | `/api/contenedores` | Lista contenedores Docker |
| GET | `/api/servicios` | Último health check por servicio |
| GET | `/api/servicios/{nombre}/historial` | Historial de un servicio |
| GET | `/api/alertas` | Alertas (módulo medido) |
| POST | `/api/alertas/{id}/resolver` | Resolver alerta |
| DELETE | `/api/alertas/{id}` | Eliminar alerta |
| POST | `/api/claude/sesion` | Recibe evento hook Stop (idempotente) |
| GET | `/api/claude/resumen` | Agrega por período: día/semana/mes con presupuesto |
| GET | `/api/claude/sesiones` | Lista sesiones con filtros |
| DELETE | `/api/claude/sesiones/{session_id}` | Elimina sesión |

## Variables de entorno

| Variable | Descripción |
|----------|-------------|
| `MEDIDO_DB_PATH` | Ruta BD SQLite (defecto `data/medido.db`) |
| `PVE_HOST` | IP Proxmox |
| `PVE_NODE` | Nombre nodo Proxmox (`deeloco`) |
| `PVE_TOKEN_ID` | Token API (`root@pam!medido`) |
| `PVE_TOKEN_SECRET` | Secret del token |
| `PVE_VERIFY_SSL` | Verificar SSL (defecto `false`) |
| `NTFY_TOPIC` | Topic NTFY (`hogaros-3ca6f61b`) |
| `MEDIDO_INTERVALO_HEALTH` | Intervalo health checks en segundos (defecto 60) |
| `MEDIDO_INTERVALO_METRICAS` | Intervalo métricas en segundos (defecto 300) |
| `MEDIDO_DIAS_RETENCION` | Días de historial (defecto 90) |
| `CLAUDE_PRESUPUESTO_EUR` | Presupuesto mensual Claude Code en EUR |
| `CLAUDE_DIA_RESETEO` | Día del mes de reseteo 1-31 (defecto 1) |

## hogar.css
Nginx reescribe `/static/` → `/salud/static/` y lo sirve desde `portal/static/` de hogarOS.
