# CLAUDE.md — MediDo

## Que es

**MediDo** (Metricas Domesticas) es la app de monitorizacion del ecosistema hogarOS.
Recolecta metricas de Proxmox, estado de contenedores Docker, health checks de servicios
y genera alertas proactivas via NTFY.

- **GitHub:** acabellan1868-prog/MediDo
- **Ruta local:** `Desarrollo/MediDo/`
- **En el servidor:** `/mnt/datos/medido-build/` (git clone, build context Docker)
- **Datos persistentes:** `/mnt/datos/medido/medido.db`

---

## Estructura del repo

```
MediDo/
├── app/
│   ├── principal.py             → Punto de entrada FastAPI + APScheduler
│   ├── bd.py                    → Acceso a SQLite (medido.db)
│   ├── config.py                → Variables de entorno
│   ├── esquema.sql              → DDL de la base de datos
│   ├── recolector_proxmox.py    → Metricas via Proxmox API REST
│   ├── recolector_docker.py     → Estado de contenedores via Docker SDK
│   ├── health_checker.py        → Comprobaciones HTTP periodicas
│   ├── alertador.py             → Logica de umbrales + NTFY
│   └── rutas/
│       ├── resumen.py           → GET /api/resumen (tarjeta portal)
│       ├── proxmox.py           → GET /api/proxmox + historial
│       ├── contenedores.py      → GET /api/contenedores
│       ├── servicios.py         → GET /api/servicios + historial
│       └── alertas.py           → GET/POST /api/alertas
├── static/
│   └── index.html               → Frontend completo (SPA vanilla)
├── data/
│   └── .gitkeep                 → La BD medido.db se crea aqui en runtime
├── Dockerfile
└── requirements.txt
```

---

## Integracion con hogarOS

MediDo se sirve en `/salud/` a traves del Nginx de hogarOS.

**Puerto:** 8084 (configurable via env)
**Red Docker:** bridge normal + `extra_hosts` para acceso al host

### hogar.css

Mismo mecanismo que ReDo y FiDo: Nginx reescribe `/static/` a `/salud/static/`
y lo sirve desde `portal/static/` del repo hogarOS.

---

## Fuentes de datos

| Fuente | Metodo | Datos |
|---|---|---|
| Proxmox API | HTTPS con API Token | CPU, RAM, disco, VMs, almacenamiento |
| Docker SDK | Socket montado `:ro` | Contenedores, estado, uptime |
| HTTP health checks | httpx GET | Estado y latencia de cada servicio |
| hogar-api | HTTP interno | Estado de backups |

---

## API

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/api/resumen` | Estado global para la tarjeta del portal |
| GET | `/api/proxmox` | Metricas actuales de Proxmox (host + VMs + storage) |
| GET | `/api/proxmox/historial?horas=24` | Serie temporal de metricas |
| GET | `/api/contenedores` | Lista de contenedores Docker |
| GET | `/api/servicios` | Ultimo health check de cada servicio |
| GET | `/api/servicios/{nombre}/historial` | Historial de un servicio |
| GET | `/api/alertas` | Alertas activas y recientes |
| POST | `/api/alertas/{id}/resolver` | Marcar alerta como resuelta |

---

## Variables de entorno

| Variable | Descripcion |
|---|---|
| `MEDIDO_DB_PATH` | Ruta a la BD SQLite (defecto `data/medido.db`) |
| `PVE_HOST` | IP del servidor Proxmox |
| `PVE_NODE` | Nombre del nodo Proxmox |
| `PVE_TOKEN_ID` | Token API (usuario!token) |
| `PVE_TOKEN_SECRET` | Secret del token API |
| `PVE_VERIFY_SSL` | Verificar SSL (defecto `false`) |
| `HA_TOKEN` | Token de Home Assistant (opcional) |
| `NTFY_TOPIC` | Topic de NTFY para alertas |
| `MEDIDO_INTERVALO_HEALTH` | Intervalo health checks en segundos (defecto 60) |
| `MEDIDO_INTERVALO_METRICAS` | Intervalo metricas en segundos (defecto 300) |
| `MEDIDO_DIAS_RETENCION` | Dias de historial a mantener (defecto 90) |

---

## Convenciones de codigo

- Todo en espanol: variables, funciones, clases, comentarios
- Backend: Python + FastAPI + SQLite
- Frontend: HTML/CSS/JS vanilla, sin frameworks ni bundlers
- Design system: Living Sanctuary (hogar.css)
