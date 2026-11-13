# Estado de la arquitectura frente al diseño del Sprint 0

Comparación componente por componente entre la arquitectura propuesta en el Sprint 0 (secciones 4 y 5, componentes C1 a C27) y lo que hay en el código. Sirve para saber qué está hecho, qué cambió a propósito y qué falta de verdad.

Leyenda: **Hecho** = existe y está probado · **Cambió** = se hizo distinto al diseño, con motivo · **Pendiente** = no existe.

## Capa de presentación

| # | Diseño | Estado | Notas |
|---|---|---|---|
| C1 | SPA React + TypeScript | Hecho | Vite, React 18, React Router |
| C2 | Cliente OIDC (MSAL.js) | **Pendiente** | El inicio de sesión es local (correo y contraseña, HU-01 a HU-03). Ver "Decisiones abiertas" |
| C3 | Exportación en cliente (`file-saver`) | Cambió | El archivo lo genera el backend y el navegador lo descarga con `fetch`; no se usa `file-saver` |

## Capa de aplicación

| # | Diseño | Estado | Notas |
|---|---|---|---|
| C4 | API REST (FastAPI) | Hecho | Pydantic v2, SQLAlchemy 2.0 |
| C5 | Identidad y autorización (Entra ID) | Cambió / Pendiente | RBAC por endpoint y JWT propio con `pyjwt`, no `python-jose`. La federación con Entra ID no existe; `usuarios.id_entra` y `security.py` dejan el espacio previsto |
| C6 | Solicitudes | Hecho | Borrador, duplicar, cliente obligatorio, ajuste y reejecución |
| C7 | Sincronización con OneDrive | Hecho y ampliado | Además de Microsoft Graph, Google Drive; el administrador elige el proveedor |
| C8 | Extracción de documentos | Hecho | PDF, DOCX, DOC; OCR de respaldo con Tesseract |
| C9 | Indexación | Cambió | Fragmentación propia (`loaders/chunker.py`), no LangChain; embeddings de OpenAI; pgvector |
| C10 | Motor de matching | Hecho | Recuperación híbrida (vectorial + léxica) con RRF, filtrado y re-ranking con el LLM. La parte léxica usa `tsvector`/`ts_rank`, no BM25 |
| C11 | Adaptador del servicio de IA | Cambió | **OpenAI** para LLM y embeddings (el diseño decía Anthropic Claude). Reintentos con backoff y salida JSON validada; sin la librería Instructor |
| C12 | Exportación PDF y XLSX | Cambió | `fpdf2` en lugar de WeasyPrint (sin dependencias de sistema); `openpyxl` para Excel |
| C13 | Bitácora y auditoría | Hecho | Registro explícito desde los servicios, no con listeners de SQLAlchemy; consulta paginada y filtrada (HU-06) |
| C14 | Configuración | Hecho | Parámetros en tabla (HU-07); se leen en cada búsqueda, sin caché en memoria |

## Procesamiento asíncrono

| # | Diseño | Estado | Notas |
|---|---|---|---|
| C15 | Cola de trabajos (Redis + RQ) | Hecho | Si Redis o el worker faltan, el trabajo corre en la API; probado también con Redis caído en plena ejecución. Ver `redis-y-worker.md` |
| C16 | Worker de ingesta | Hecho | |
| C17 | Worker de búsqueda | Hecho | |
| C18 | Planificador | Hecho | APScheduler dentro del worker (`--planificador`), un solo proceso |

## Capa de datos

| # | Diseño | Estado | Notas |
|---|---|---|---|
| C19 | PostgreSQL 16 | Hecho | Migraciones con Alembic. Ver `base-de-datos.md` |
| C20 | pgvector con índice HNSW | Hecho | Índice creado por la migración `0002` y verificado con `EXPLAIN` |
| C21 | Índice léxico `tsvector` + GIN | Hecho | Idem |
| C22 | Caché (Redis) | **Cambió, parcial** | Solo el embedding de las consultas repetidas. Las sesiones son JWT sin estado y el progreso de las búsquedas está en PostgreSQL: no se pasaron a Redis porque con menos de 10 usuarios no aportan nada y suman un punto de fallo |
| C23 | Gestor de secretos | Cambió | `.env.production` con permisos `600` y copia en AWS Systems Manager Parameter Store (`scripts/aws/secretos-ssm.sh`); no Key Vault. La copia en Parameter Store no se probó contra AWS real |

## Sistemas externos

| # | Diseño | Estado | Notas |
|---|---|---|---|
| E1 | OneDrive / SharePoint | Hecho (más Google Drive) | Solo lectura |
| E2 | Microsoft Entra ID | **Pendiente** | Ver C2 y C5 |
| E3 | Servicio de IA | Cambió | OpenAI |

## Infraestructura y soporte

| # | Diseño | Estado | Notas |
|---|---|---|---|
| C24 | Contenedores | Hecho | `docker-compose.yml` (desarrollo) y `docker-compose.prod.yml` (producción) |
| C25 | CI/CD (GitHub Actions) | **CI hecho, CD pendiente** | Ruff, pytest (SQLite, PostgreSQL y Redis reales), lint y compilación del frontend en cada PR. El despliegue es manual con `scripts/aws/desplegar.sh`, a propósito: con una sola instancia y un equipo pequeño no hay un pipeline que valga lo que cuesta mantenerlo |
| C26 | Hosting | Cambió | Una EC2 con Docker Compose (AWS) en lugar de Azure Container Apps/Render + PostgreSQL gestionado. Motivo y costos en `despliegue-aws.md` |
| C27 | Observabilidad (`structlog`, Sentry, métricas) | **Cambió, parcial** | Logs JSON con id de petición (biblioteca estándar, no `structlog`) y Sentry opcional. **Pendiente:** métricas de latencia y consumo de tokens como serie (hoy el consumo de tokens queda por búsqueda en la base) |

## Decisiones abiertas

1. **Inicio de sesión corporativo con Entra ID (C2, C5, E2).** No es trabajo de infraestructura sino de producto: los Sprints 1 a 3 implementaron autenticación local (HU-01 a HU-03, dominio `@bee.com.co`, bloqueo tras 5 intentos) y no se ha pedido migrarla. Hacerlo exige un *tenant* de Microsoft con permisos para registrar la aplicación, al que el equipo no tiene acceso; sin él no se puede probar. Si se decide, el punto de entrada ya está previsto (`id_entra`, `password_hash` nulo para usuarios federados).
2. **Despliegue continuo.** Hoy es manual (`desplegar.sh`). Automatizarlo exige guardar una llave SSH como secreto del repositorio; se pospone hasta que el despliegue manual deje de ser razonable.
3. **Métricas.** Si se quieren paneles de latencia y costo de tokens, la opción más barata es exportar desde la tabla `busquedas` (ya guarda duración, modelo y tokens por ejecución).
4. **PostgreSQL gestionado.** Con Compose la base vive en la misma instancia. Si el proyecto sigue más allá del semestre, pasar a RDS es cambiar `DATABASE_URL` y restaurar un respaldo (ver `despliegue-aws.md`).

## Lo que se hizo para cerrar la brecha

| Tema | Documento |
|---|---|
| CI, ruff en cero | `.github/workflows/ci.yml` |
| PostgreSQL, pgvector, índices, migración de datos, Alembic | [`base-de-datos.md`](base-de-datos.md) |
| Redis, worker, planificador, caché | [`redis-y-worker.md`](redis-y-worker.md) |
| Despliegue, costos, observabilidad, secretos | [`despliegue-aws.md`](despliegue-aws.md) |
