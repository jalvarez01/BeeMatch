# BeeMatch — contexto de trabajo

Asistente de preselección de talento para Bee Consultoría y Negocios S.A.S.
Proyecto Integrador 2, EAFIT. Backend FastAPI + SQLAlchemy, frontend React/Vite.
Un reclutador describe el perfil en lenguaje natural y BeeMatch devuelve los
cinco candidatos con mayor afinidad, con evidencia del CV que la sustenta.

## Cómo trabajar en este repo

- **Alcance estricto.** Hacer lo que se pide y nada más. No arreglar TODOs, no
  refactorizar de paso, no implementar historias que nadie pidió. Si algo más
  parece roto, se menciona en una línea y se sigue con lo pedido.
- **Nunca "continuar" sin contexto.** Si el estado de la conversación no dice en
  qué se estaba trabajando, preguntar; no deducirlo del último commit.
- **Antes de tocar código, confirmar.** Revisar y reportar es gratis; editar no.
  Cuando el usuario dice "solo revisa", solo se lee.
- **`.env` y credenciales:** nunca imprimir el valor de una clave en la
  terminal. Se reporta longitud, prefijo o si está vacía. `.env` y
  `beematch-credenciales.json` están en `.gitignore` y así se quedan.
- **Idioma:** todo en español —nombres, docstrings, comentarios, mensajes de
  error de cara al usuario. Los comentarios explican el *por qué* y citan la
  historia o el requisito (HU-05, RNF10, RD3...), no narran el código.

## Entorno

- **No hay `python` en el PATH.** Usar `.venv/bin/python`.
- Para ejecutar scripts sueltos contra el backend: `PYTHONPATH="$PWD" .venv/bin/python ...`
- Los archivos temporales van al scratchpad de la sesión, no al repo ni a `/tmp`.
- `backend/**/__pycache__/*.pyc` están **versionados** (se commitearon antes de
  que existiera la regla en `.gitignore`). Importar módulos los modifica y
  aparecen en `git status`; se restauran con `git checkout -- <ruta>`. Revisar
  que el árbol quede limpio antes de dar algo por terminado.

## Arquitectura

Dependencia en una sola dirección: `api → domain → infrastructure`. Un router
nunca toca la base de datos; un repositorio nunca conoce FastAPI.

- `backend/api/` routers · `backend/schemas/` contratos Pydantic
- `backend/domain/services/` lógica de negocio · `backend/domain/matching/`
  motor de afinidad en 3 etapas (retriever híbrido con RRF → filtro duro en SQL
  → re-ranking con LLM sobre ~20 finalistas)
- `backend/infrastructure/` `llm/` (Anthropic para re-ranking, OpenAI para
  embeddings), `loaders/` (pypdf, python-docx, chunker), `repositorio/`
  (contrato + factory), `gdrive/`, `onedrive/`, `persistence/`
- `backend/workers/` cola RQ, worker de ingesta, worker de búsqueda, planificador

Regla de producto que no se negocia: toda coincidencia mostrada cita el
fragmento del CV que la respalda. Si el requisito no aparece, es
`NO_EVIDENCIADO` = *el documento no lo menciona*, nunca *el candidato no lo
tiene*. La salvaguarda está en `domain/matching/reranker.py`.

## Estado al 18 de septiembre de 2026

Rama `juanjobranch`, último commit `de7e167`.

**HU-05 (configuración del repositorio de hojas de vida) está completa y
verificada** contra los cinco criterios de aceptación. El origen real es
**Google Drive**, no OneDrive: el servicio es genérico
(`TIPOS_VALIDOS = (ONEDRIVE, GDRIVE)`) y los endpoints `/configuracion/onedrive`
conviven con los genéricos `/configuracion/repositorio`, que son los que usa el
frontend. La justificación del cambio de proveedor está en la wiki del curso.

- Cuenta de servicio `beematch-lector@beematch-508419.iam.gserviceaccount.com`,
  carpeta `1H7-p-d3auJOzrw660zGfmKa5drW0Hn_V`, **30 CVs** detectados (PDF).
- La semilla de arranque (`backend/main.py:_sembrar_repositorio`) registra esa
  conexión al startup si no hay ninguna activa, pasando por
  `RepositorioConfigService.guardar` (validación + cifrado Fernet).
- `data/beematch.db` (SQLite local): config activa `GDRIVE`, 30 hojas en estado
  `PENDIENTE`, 0 candidatos, 0 fragmentos, 3 usuarios.

**Claves de IA (`.env`):** `EMBEDDING_API_KEY` ya está puesta y probada contra
OpenAI (vectores de 1536 dimensiones, `text-embedding-3-small`). En cambio
`LLM_API_KEY` tiene una clave de **OpenAI** y `LLM_MODELO=gpt-4o-mini`, pero
`ProveedorLLM` habla por el SDK de **Anthropic**: la etapa 3 del motor
(re-ranking y explicación) fallará. Salidas posibles: clave de Anthropic con
`LLM_MODELO=claude-opus-5`, o reescribir `llm_provider.py` contra OpenAI. Sin
decisión del usuario, no tocar.

**Pendiente de implementar** (no empezar sin que lo pidan):

- `domain/services/indexacion_service.py:73` — `TODO(Sprint 2)`: el perfil
  estructurado sale de una heurística sobre el nombre del archivo. Falta
  extraerlo con el LLM (RF02). Consecuencia hoy: `rol_principal`,
  `anios_experiencia`, `ubicacion` e `idiomas` quedan en `None` y
  `CandidatoRepository.reemplazar_habilidades` no se llama desde ningún sitio,
  así que la tabla `habilidades` está vacía y el filtro por experiencia mínima
  (`domain/matching/filtros.py`) descarta a todos los candidatos con `NULL`.
- `domain/services/export_service.py:56` — exportación a PDF, Sprint 3. La de
  XLSX ya funciona.

**Dependencias declaradas pero no instaladas en `.venv`:** `rq`, `redis`,
`apscheduler`, `weasyprint`, `pytesseract`/`pdf2image`, `pdfplumber` (esta
última está en `requirements.txt` y ningún módulo la importa). Efectos: el
planificador no arranca (`main.py` lo condiciona a que APScheduler exista) y
`workers/queue.py:encolar` ejecuta los trabajos **en línea** dentro de la
petición HTTP cuando Redis no está disponible —diseñado así, sirve para
desarrollo—. Sin Redis la indexación de los 30 CVs corre síncrona en
`POST /hojas-vida/sincronizar` (unos 2-3 minutos) y las búsquedas pierden la
barra de progreso que promete HU-18.

`cryptography==50.0.1` se agregó a `requirements.txt`: es lo que hace el
cifrado de HU-05 y antes solo llegaba como dependencia transitiva.

## Pruebas

`pytest.ini` (`pythonpath = .`, `testpaths = tests`) y `tests/`. Se ejecutan con
`.venv/bin/python -m pytest`. Cuatro pruebas de HU-05, todas offline.

Convenciones del andamiaje (`tests/conftest.py`):

- `DATABASE_URL` se fija a un SQLite temporal **antes** de importar `backend`,
  porque el engine se construye al importar el módulo de persistencia. Las
  pruebas nunca tocan `data/beematch.db`.
- Ninguna prueba sale a la red: `ClienteFalso` implementa el contrato
  `RepositorioDocumentos` y la fixture `origen` reemplaza `crear_cliente` en
  `repositorio_config_service` para simular que el proveedor acepta o rechaza.
- El `TestClient` se instancia **sin** gestor de contexto, para que no corra el
  startup de FastAPI (semilla del repositorio y planificador).
- Las dependencias `get_db` y `get_current_user` se sobreescriben con
  `app.dependency_overrides`; hay una fixture `administrador` con rol real.

Una prueba nueva se valida rompiendo a propósito lo que cubre y comprobando que
falle; después se restaura con `git checkout`.

## Detalles que ya se revisaron y conviene recordar

- `ENCRYPTION_KEY` está vacía, así que la llave de cifrado se deriva de
  `JWT_SECRET` (`infrastructure/crypto.py`). Funciona, pero si alguien cambia
  `JWT_SECRET` la configuración guardada queda ilegible: `obtener()` lo maneja
  devolviendo `secreto_legible: false`, mientras `cliente_activo()` deja subir
  el `CifradoError` crudo y la sincronización lo reporta como 502 genérico.
- `@app.on_event("startup")` está deprecado en FastAPI 0.115; el reemplazo es
  `lifespan`. Funciona, solo emite DeprecationWarning en las pruebas.
- Google Drive no tiene delta por carpeta: `listar_documentos` recorre todo y
  devuelve `None` como cursor. Los cambios se detectan por `md5Checksum`, y por
  `modifiedTime` en los Google Docs nativos, que no exponen checksum.
