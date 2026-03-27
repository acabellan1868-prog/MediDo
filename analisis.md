# Análisis — MediDo (Métricas Domésticas)

## Qué es

MediDo es la app de monitorización del ecosistema **hogarOS**. Recopila métricas
del servidor (Proxmox), estado de contenedores Docker, comprueba la disponibilidad
de los servicios y genera alertas cuando algo falla o supera umbrales configurados.

## Por qué se hace

El ecosistema hogarOS tiene múltiples servicios distribuidos en una VM. Sin
monitorización centralizada:
- Hay que entrar a Portainer para ver qué contenedores están caídos.
- Hay que acceder a Proxmox para ver CPU, RAM y disco.
- No hay alertas proactivas cuando un servicio falla.

MediDo proporciona una vista unificada y alertas automáticas vía ntfy.

## Stack

| Capa | Tecnología |
|------|------------|
| Backend | Python + FastAPI + APScheduler |
| Frontend | HTML/CSS/JS vanilla (SPA) |
| Métricas Proxmox | Proxmox API REST |
| Estado Docker | Docker SDK for Python |
| Health checks | requests HTTP |
| Alertas | ntfy |
| Base de datos | SQLite |
| Despliegue | Docker (puerto 8084) |
| Proxy | Nginx de hogarOS en `/salud/` |

## Decisiones de diseño

### Proxmox API vs SSH
Se usa la API REST de Proxmox. Es más limpia, bien documentada y devuelve
exactamente lo necesario (CPU, RAM, disco, estado de VMs). SSH descartado por
innecesario.

### Docker SDK vs Docker API HTTP
Se usa el SDK oficial de Python (`docker`), accediendo al socket
`/var/run/docker.sock` montado como volumen de solo lectura. Alternativa de
acceso HTTP directo descartada por innecesaria.

### SQLite para persistencia
Mismo patrón que ReDo y FiDo. Tres tablas: métricas históricas, health_checks,
alertas. Limpieza nocturna a 90 días para no crecer indefinidamente.

### Deduplicación de alertas: ventana de 1 hora
Una alerta del mismo tipo/servicio no se repite si ya existe una activa de menos
de 1 hora. Evita spam pero implica renotificación cada hora para problemas
persistentes. A revisar si el comportamiento resulta molesto en producción.

### Health checks: host.docker.internal vs IP LAN
Los health checks de servicios con `network_mode: host` (ReDo) deben usar
`http://host.docker.internal:8083`, que resuelve al gateway del bridge de
docker-compose. La IP LAN (`192.168.31.131`) falla por el routing bridge→LAN.
Ver gotcha en el CLAUDE.md global.
