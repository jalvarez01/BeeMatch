# BeeMatch

Asistente inteligente de preselección de talento para **Bee Consultoría y Negocios S.A.S.**
Proyecto Integrador 2 · EAFIT

Un reclutador describe el perfil que necesita en lenguaje natural; BeeMatch analiza las hojas de
vida del repositorio corporativo de OneDrive y devuelve los cinco candidatos con mayor afinidad,
con la explicación de las coincidencias y la ubicación de cada documento.

---

## Estructura del proyecto

```
BeeMatch/
├── backend/
│   ├── api/                        Routers de FastAPI (capa de entrada)
│   ├── schemas/                    Contratos de entrada y salida (Pydantic)
│   ├── domain/
│   │   ├── services/               Lógica de negocio
│   │   └── matching/               Motor de afinidad en 3 etapas
│   ├── infrastructure/
│   │   ├── llm/                    Adaptador del servicio de IA y embeddings
│   │   ├── loaders/                Extracción de PDF/DOCX y fragmentación
│   │   ├── onedrive/               Microsoft Graph (solo lectura)
│   │   └── persistence/
│   │       ├── models/             Modelos ORM
│   │       └── repositories/       Acceso a datos
│   ├── workers/                    Procesamiento asíncrono (cola RQ)
│   ├── config.py                   Configuración desde el entorno
│   ├── security.py                 JWT y control de acceso por roles
│   └── main.py                     Ensamblado de la aplicación
│
├── frontend/
│   └── src/
│       ├── api/                    Cliente HTTP por recurso
│       ├── components/             Layout, sidebar, badges, progreso
│       ├── pages/                  Una pantalla por archivo
│       ├── styles/                 Hoja de estilos derivada de los mockups
│       └── types.ts                Tipos espejo de los schemas del backend
│
├── data/                           Base de datos local (desarrollo)
├── storage/                        Archivos exportados
└── docker-compose.yml
```

La dependencia va en una sola dirección: `api → domain → infrastructure`. Un router nunca toca
la base de datos directamente y un repositorio nunca conoce FastAPI.

---

## Cómo funciona

**Flujo 1 — Indexación (corre en segundo plano, una sola vez por documento)**

El planificador consulta OneDrive con *delta queries*, detecta qué archivos son nuevos o
cambiaron y los encola. El worker de ingesta descarga cada uno en memoria, extrae el texto,
lo parte en fragmentos y genera sus *embeddings*. No se copian los archivos: se guarda el texto
indexado y la referencia al documento, porque OneDrive sigue siendo la única fuente de verdad.

**Flujo 2 — Búsqueda (camino crítico, menos de 2 minutos)**

1. **Recuperación híbrida** — búsqueda léxica (términos exactos como "Spring Boot") fusionada con
   búsqueda vectorial (equivalencias como "core bancario") mediante Reciprocal Rank Fusion.
2. **Filtrado duro** — los criterios obligatorios y la experiencia mínima se resuelven en SQL.
3. **Re-ranking con IA** — solo los ~20 finalistas se envían al modelo, que los ordena y explica.

Enviar las 200 hojas de vida completas al modelo costaría unos 300.000 tokens por consulta. Con
recuperación previa la cifra baja a unos 30.000.

**Explicabilidad**

Cada coincidencia mostrada apunta al fragmento del CV que la sustenta. Si un requisito no aparece
en el documento, se marca `NO_EVIDENCIADO`, que significa *la hoja de vida no lo menciona* — nunca
*el candidato no lo tiene*. Esa validación está en `domain/matching/reranker.py` y es obligatoria:
una coincidencia sin fragmento de respaldo se degrada automáticamente.

---

## Puesta en marcha

### Con Docker

```bash
cp .env.example .env      # completar credenciales
docker compose up --build
```

API en `http://localhost:8000/docs`, frontend en `http://localhost:5173`.

### Manual

**Backend**

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

Sin `DATABASE_URL` usa SQLite y funciona sin PostgreSQL. Sin `REDIS_URL` los trabajos se ejecutan
en línea en vez de encolarse: sirve para desarrollo, no para producción.

**Worker** (en otra terminal, si hay Redis)

```bash
rq worker beematch --url redis://localhost:6379/0
```

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

---

## Variables de entorno

| Variable | Para qué |
|---|---|
| `DATABASE_URL` | PostgreSQL + pgvector. Si se omite, SQLite local. |
| `REDIS_URL` | Cola de trabajos. |
| `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET` | App registrada en Entra ID. |
| `ONEDRIVE_DRIVE_ID`, `ONEDRIVE_CARPETA_CV` | Ubicación del repositorio de hojas de vida. |
| `LLM_API_KEY`, `LLM_MODELO` | Servicio de IA. |
| `TOP_N_RESULTADOS`, `FINALISTAS_RERANK`, `UMBRAL_AFINIDAD_MINIMA` | Motor de matching. |
| `JWT_SECRET` | Firma de tokens. Cambiar en producción. |

Los permisos sobre OneDrive deben ser **solo lectura** y limitados a la carpeta de hojas de vida.

---

## Pendiente de implementar

Tres puntos están marcados con `TODO` y son el trabajo del Sprint 1:

- `infrastructure/llm/embeddings.py` → llamada real al proveedor de embeddings.
- `infrastructure/llm/llm_provider.py` → llamada real al modelo de lenguaje.
- `domain/services/indexacion_service.py` → extracción del perfil estructurado con IA (hoy es una
  heurística sobre el nombre del archivo).

La exportación a PDF (`domain/services/export_service.py`) está prevista para el Sprint 3; la
exportación a XLSX ya funciona.

---

## Pantallas

| Ruta | Archivo | Historias |
|---|---|---|
| `/login` | `pages/Login.tsx` | HU-01, HU-02 |
| `/inicio` | `pages/Dashboard.tsx` | — |
| `/nueva-busqueda` | `pages/NuevaBusqueda.tsx` | HU-08 a HU-12, HU-15 |
| `/resultados/:busquedaId` | `pages/Resultados.tsx` | HU-17, HU-18, HU-20, HU-22 a HU-25 |
| `/candidato/:recomendacionId` | `pages/Candidato.tsx` | HU-19, HU-21, HU-24 |
| `/historial` | `pages/Historial.tsx` | HU-13, HU-14 |
| `/solicitudes` | `pages/Solicitudes.tsx` | — |
| `/candidatos` | `pages/Candidatos.tsx` | HU-16 |
| `/configuracion` | `pages/Configuracion.tsx` | HU-05, HU-06, HU-07 |
