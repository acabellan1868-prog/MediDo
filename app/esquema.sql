-- MediDo — Esquema de base de datos
-- Metricas del sistema, health checks y alertas

PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

-- Snapshots periodicos del estado del sistema (Proxmox + Docker)
CREATE TABLE IF NOT EXISTS metricas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL DEFAULT (datetime('now')),
    -- Host Proxmox
    pve_cpu_percent REAL,
    pve_memoria_percent REAL,
    pve_memoria_usado_gb REAL,
    pve_memoria_total_gb REAL,
    pve_uptime_dias REAL,
    -- VM principal (101)
    vm_cpu_percent REAL,
    vm_memoria_percent REAL,
    vm_memoria_usado_gb REAL,
    vm_memoria_total_gb REAL,
    vm_disco_percent REAL,
    vm_disco_usado_gb REAL,
    vm_disco_total_gb REAL,
    vm_uptime_dias REAL,
    -- Contenedores Docker
    contenedores_total INTEGER,
    contenedores_running INTEGER,
    contenedores_stopped INTEGER
);

-- Historial de health checks
CREATE TABLE IF NOT EXISTS health_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT NOT NULL DEFAULT (datetime('now')),
    servicio TEXT NOT NULL,
    estado TEXT NOT NULL CHECK(estado IN ('ok', 'lento', 'caido', 'error')),
    tiempo_respuesta_ms INTEGER,
    codigo_http INTEGER,
    mensaje TEXT
);

-- Alertas de MediDo
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    mensaje TEXT NOT NULL,
    servicio TEXT,
    fecha TEXT NOT NULL DEFAULT (datetime('now')),
    enviada INTEGER NOT NULL DEFAULT 0,
    resuelta INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_metricas_fecha ON metricas(fecha);
CREATE INDEX IF NOT EXISTS idx_health_fecha ON health_checks(fecha);
CREATE INDEX IF NOT EXISTS idx_health_servicio ON health_checks(servicio);
CREATE INDEX IF NOT EXISTS idx_alertas_fecha ON alertas(fecha);
