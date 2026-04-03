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

-- Tracking de sesiones de Claude Code (desde hook en Windows)
CREATE TABLE IF NOT EXISTS tracking_claude (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    -- Datos del hook de Claude Code
    session_id TEXT NOT NULL,
    fecha_fin TEXT NOT NULL,                    -- ISO 8601 con timezone (del hook)
    directorio TEXT,                            -- C:\Users\... (opcional)
    proyecto TEXT NOT NULL,                     -- Identificador del proyecto
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_creation_tokens INTEGER NOT NULL DEFAULT 0,
    coste_input_usd REAL NOT NULL DEFAULT 0.0,
    coste_output_usd REAL NOT NULL DEFAULT 0.0,
    coste_cache_usd REAL NOT NULL DEFAULT 0.0,
    -- Metadatos en MediDo
    fecha_registro TEXT NOT NULL DEFAULT (datetime('now')),   -- UTC de recepcion
    sincronizado INTEGER NOT NULL DEFAULT 0,                  -- 0=pendiente, 1=enviado desde cola
    -- Restricciones de validacion
    CHECK(input_tokens >= 0),
    CHECK(output_tokens >= 0),
    CHECK(cache_read_tokens >= 0),
    CHECK(cache_creation_tokens >= 0),
    CHECK(coste_input_usd >= 0),
    CHECK(coste_output_usd >= 0),
    CHECK(coste_cache_usd >= 0)
);

-- Indices para búsquedas eficientes
CREATE INDEX IF NOT EXISTS idx_metricas_fecha ON metricas(fecha);
CREATE INDEX IF NOT EXISTS idx_health_fecha ON health_checks(fecha);
CREATE INDEX IF NOT EXISTS idx_health_servicio ON health_checks(servicio);
CREATE INDEX IF NOT EXISTS idx_alertas_fecha ON alertas(fecha);
CREATE INDEX IF NOT EXISTS idx_claude_sesion ON tracking_claude(session_id);
CREATE INDEX IF NOT EXISTS idx_claude_fecha_fin ON tracking_claude(fecha_fin);
CREATE INDEX IF NOT EXISTS idx_claude_fecha_registro ON tracking_claude(fecha_registro);
CREATE INDEX IF NOT EXISTS idx_claude_proyecto ON tracking_claude(proyecto);
