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

## Health checks — URLs y notas

| Servicio | URL | Notas |
|---|---|---|
| portal | `http://host.docker.internal:80/` | Nginx del portal |
| fido | `http://fido:8080/api/resumen` | Por nombre de contenedor (misma red bridge) |
| redo | `http://host.docker.internal:8083/api/resumen` | `network_mode:host` → usar host.docker.internal, NO la IP LAN ni 192.168.x.x |
| hogar-api | `http://hogar-api:8080/lanzador` | Por nombre de contenedor |
| home-assistant | `http://192.168.31.132:8123/api/` | IP directa; acepta 200 y 401 |
| kryptonite | `http://host.docker.internal:5000/portafolio` | Servicio en el host |
| nextcloud | `http://host.docker.internal:8081/status.php` | Acepta 200 y 400 (rechaza HTTP plano con trusted_domains) |
| portainer | `http://192.168.31.131:9000/api/status` | HTTP en puerto 9000, no HTTPS 9443 |

### Por que redo usa host.docker.internal y no la IP LAN

ReDo corre con `network_mode: host`, sin mapeo de puertos (`ports:`).
Docker no crea reglas iptables para ese caso, por lo que el trafico
desde la red bridge al IP LAN del host (192.168.31.131:8083) es rechazado.
`host.docker.internal` resuelve al gateway del bridge (172.28.0.1),
que si es alcanzable desde los contenedores — igual que hace nginx.

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
| GET | `/api/alertas` | Alertas: `modulo: "medido"`, activas primero, limite 50 |
| POST | `/api/alertas/{id}/resolver` | Marcar alerta como resuelta |
| DELETE | `/api/alertas/{id}` | Eliminar alerta |
| **POST** | **`/api/claude/sesion`** | **Recibe evento de Claude Code (hook), guarda en BD (idempotente)** |
| **GET** | **`/api/claude/resumen`** | **Agrega sesiones por período: día/semana/mes con presupuesto** |
| **GET** | **`/api/claude/sesiones`** | **Lista sesiones individuales con filtros (periodo, proyecto, limite)** |

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
| **`CLAUDE_PRESUPUESTO_EUR`** | **Presupuesto mensual de Claude Code en EUR (opcional)** |
| **`CLAUDE_DIA_RESETEO`** | **Día del mes de reseteo del presupuesto 1-31 (defecto: 1)** |

---

## Convenciones de codigo

- Todo en espanol: variables, funciones, clases, comentarios
- Backend: Python + FastAPI + SQLite
- Frontend: HTML/CSS/JS vanilla, sin frameworks ni bundlers
- Design system: Living Sanctuary (hogar.css)
