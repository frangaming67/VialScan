# VialScan

MVP para relevar y visualizar el estado de calles con videos de recorridos. Extrae fotogramas, solicita una clasificación visual al modelo configurado, asocia posiciones GPS cuando existen y permite revisar las incidencias sobre un mapa.

## Qué incluye

- Panel Next.js en español con mapa Leaflet/OpenStreetMap, filtros, detalle y revisión humana.
- API FastAPI para sesiones, cargas, estado de procesamiento, consultas y revisión de incidencias.
- Extracción de fotogramas con OpenCV y análisis visual mediante OpenAI Responses API.
- Guía de referencia cargada en el backend para distinguir estado general, baches, grietas, ahuellamientos, reparaciones y señales que suelen confundirse.
- Esquema PostgreSQL/PostGIS, migración inicial e índices espaciales GiST.
- Evidencias en Supabase Storage con enlaces firmados.
- Modo de demostración con datos sintéticos claramente identificados, sin credenciales externas.
- Análisis local de secuencias de fotos con un detector ONNX de daños viales, sin OpenAI ni Supabase.

La cámara en vivo queda fuera del flujo obligatorio. El MVP prioriza la carga de un video corto o una secuencia de hasta 30 imágenes y permite adjuntar un track GPX o CSV. Sin GPS, las observaciones se guardan sin georreferenciar.

## Requisitos

- Node.js 20.9 o posterior.
- Python 3.11 o posterior.
- Un proyecto Supabase con PostGIS habilitado y un bucket privado.
- Una clave de OpenAI para analizar recorridos reales.

## Ejecutar la demostración sintética

1. Copia `.env.example` a `.env`. No reemplaces valores con credenciales reales dentro del repositorio.
2. Instala y arranca el backend desde la raíz:

   ```powershell
   py -3.11 -m venv backend/.venv
   .\backend\.venv\Scripts\Activate.ps1
   pip install -r backend/requirements.txt
   python -m uvicorn app.main:app --app-dir backend --reload --env-file .env
   ```

3. En otra terminal, instala y arranca el frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

4. Abre [http://localhost:3000](http://localhost:3000). La demo incluye cinco fotos públicas de referencia con créditos en pantalla; sus clasificaciones son sintéticas. Para probar detección real, carga tus propias fotos: el backend descarga el modelo ONNX de CamThink al primer uso. El resultado local es visible y revisable, pero no se guarda en la base compartida ni se georreferencia sin un track GPS compatible. Los archivos y licencias de las fotos demo están listados en `frontend/public/demo-images/README.md`; la fuente y notas del modelo están en `backend/models/README.md`.

## Configurar Supabase y análisis real

1. En el SQL Editor de Supabase, ejecuta `backend/migrations/001_initial_schema.sql`. La migración habilita PostGIS y crea las tablas e índices espaciales.
2. En Storage, crea un bucket privado llamado `road-evidence` (o cambia `SUPABASE_STORAGE_BUCKET`). El backend usa la clave `service_role`; mantenla solo en `.env` local y nunca la expongas al frontend.
3. Completa `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY` y `OPENAI_MODEL` en `.env`.
4. Reinicia el backend. La pantalla habilitará la carga de video cuando detecte las variables requeridas.

`DATABASE_URL` debe ser una cadena de conexión PostgreSQL de Supabase con SSL. `OPENAI_MODEL` se configura en un solo lugar y debe admitir entrada de imágenes y salidas estructuradas.

## Formatos de entrada

- Video: MP4, MOV, AVI, WEBM o M4V, hasta `MAX_VIDEO_MB`.
- Imágenes: JPG, PNG o WEBP, hasta 30 archivos (12 MB por archivo). Para imágenes se usa el orden de carga y `FRAME_INTERVAL_SECONDS` como tiempo aproximado cuando no hay timestamps propios.
- Análisis local de fotos: `POST /api/local-analysis/images`; límite total de 30 MB por solicitud. Detecta baches y varios tipos de grieta con el modelo local, estima severidad visual y devuelve evidencia. No persiste los resultados.
- GPS: GPX con timestamps, o CSV con `latitude`, `longitude` y `elapsed_seconds`; también admite `timestamp`/`time` en lugar de tiempo relativo. Los puntos se asocian por tiempo, con interpolación únicamente entre puntos cercanos.
- Muestreo de video: `FRAME_INTERVAL_SECONDS` (2 segundos por defecto).

## Severidad, consolidación y revisión

La severidad es estimada y se calcula con una heurística versionada (`heuristic-v1`) que combina categoría, confianza y área aparente de una caja aproximada. No estima profundidad, volumen ni tamaño físico. Las observaciones consecutivas del mismo tipo se agrupan dentro de la misma sesión si el tiempo y, cuando existe, la ubicación aproximada coinciden. Cada detección original queda vinculada a su fotograma.

Las incidencias empiezan como `pending` y pueden quedar `confirmed` o `dismissed`. En el panel se puede corregir tipo, severidad y coordenadas. La región que devuelve el modelo es aproximada y se conserva como tal. La detección necesita revisión humana y no está validada para decisiones de seguridad vial.

Cada fotograma también conserva una clasificación general (`good`, `fair`, `poor`, `not_assessable`), incluso cuando no hay un defecto. La sesión resume cuántos cuadros cayeron en cada estado. La guía visual está en `backend/app/data/road_condition_guide.json`: su vocabulario se basa en categorías publicadas por RDD2022 y OpenDataNI. Se incluye atribución y licencia en ese archivo; no se descargaron ni incorporaron imágenes de esos conjuntos. Esta referencia orienta el prompt, no entrena ni valida el modelo.

## API

- `GET /api/health`, `GET /api/config`, `GET /api/demo`
- `POST /api/sessions`, `GET /api/sessions`, `GET /api/sessions/{id}`
- `POST /api/sessions/{id}/upload` (video y GPS opcional), `POST /api/sessions/{id}/images` (secuencia de imágenes y GPS opcional)
- `POST /api/local-analysis/images` (análisis de fotos en memoria, sin credenciales externas)
- `GET /api/defects` con filtros `session_id`, `review_status`, `defect_type` y `severity`
- `GET /api/defects/{id}`, `PATCH /api/defects/{id}`

El análisis se procesa con una tarea simple del backend. El estado de sesión pasa por `queued`, `processing` y `completed` o `failed`. Para documentación interactiva, abre [http://localhost:8000/docs](http://localhost:8000/docs).

## Limitaciones conocidas

- Sin las variables de Supabase y OpenAI, la carga de video, georreferenciación y persistencia compartida no están disponibles; las fotos pueden analizarse localmente y los resultados viven en la sesión actual del navegador.
- La geometría de calles de la ruta sintética del centro de Mendoza se preparó con OSRM sobre datos de OpenStreetMap. El mapa muestra atribución a OpenStreetMap.
- Los modelos multimodales pueden equivocarse en pavimentos, sombras y reflejos; se guarda su salida original y debe revisarse.
- La geolocalización asociada al fotograma es aproximada. El GPS debe estar sincronizado temporalmente con el video.
- La severidad visual no mide profundidad ni dimensiones reales. Una versión posterior podría incorporar calibración, acelerómetro, cámara estéreo o sensor de profundidad.
- El procesamiento en segundo plano vive dentro del proceso FastAPI y no usa una cola durable; reiniciar el servidor durante un análisis puede interrumpirlo.
