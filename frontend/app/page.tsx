"use client";

import dynamic from "next/dynamic";
import Image from "next/image";
import { useCallback, useEffect, useState } from "react";
import {
  Activity, AlertTriangle, ArrowUpRight, Check, Clock3, CloudUpload, FileVideo2,
  LoaderCircle, MapPin, RefreshCw, Road, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { api } from "@/lib/api";
import { loadLocalSessions, saveLocalSession } from "@/lib/local-sessions";
import type { ConfigStatus, Defect, DefectType, ReviewStatus, ScanSession, Severity } from "@/lib/types";

const RoadMap = dynamic(() => import("@/components/road-map"), {
  ssr: false,
  loading: () => <div className="map-shell grid place-items-center text-sm text-slate-500">Cargando mapa…</div>,
});

const TYPE_LABELS: Record<string, string> = {
  longitudinal_crack: "Grieta longitudinal",
  transverse_crack: "Grieta transversal",
  alligator_crack: "Fisuración tipo cocodrilo",
  pothole: "Pozo / bache",
  patch: "Parche o reparación",
  rutting: "Ahuellamiento",
  deformation: "Deformación / hundimiento",
  raveling: "Desgranamiento",
  edge_break: "Rotura de borde",
  other: "Otro defecto",
};
const SEVERITY_LABELS: Record<Severity, string> = { low: "Baja", medium: "Media", high: "Alta", unknown: "Sin estimar" };
const STATUS_LABELS: Record<ReviewStatus, string> = { pending: "Pendiente", confirmed: "Confirmado", dismissed: "Descartado" };
const CONDITION_LABELS: Record<string, string> = { good: "Buen estado visible", fair: "Deterioro leve", poor: "Deterioro marcado", not_assessable: "No evaluable" };
const CONDITION_COLORS: Record<string, string> = { good: "#55a27b", fair: "#e4ac4c", poor: "#d95d50", not_assessable: "#9aa7a9" };
const STATUS_COPY: Record<string, string> = {
  created: "Creada", queued: "En cola", processing: "Analizando", completed: "Completado", failed: "Error",
};

function formatTime(seconds: number) {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remaining = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remaining}`;
}

export default function HomePage() {
  const [sessions, setSessions] = useState<ScanSession[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [config, setConfig] = useState<ConfigStatus | null>(null);
  const [synthetic, setSynthetic] = useState(true);
  const [typeFilter, setTypeFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [name, setName] = useState("Recorrido nuevo");
  const [video, setVideo] = useState<File | null>(null);
  const [images, setImages] = useState<File[]>([]);
  const [gps, setGps] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<{ text: string; kind: "error" | "success" | "info" } | null>(null);
  const [loading, setLoading] = useState(true);

  const loadDemo = useCallback(async () => {
    const [demo, localSessions] = await Promise.all([
      api.demo(), loadLocalSessions().catch(() => []),
    ]);
    const combined = [...localSessions, ...demo.sessions];
    setSessions(combined);
    setActiveId(demo.sessions[0]?.id ?? localSessions[0]?.id ?? null);
    setSelectedId(demo.sessions[0]?.defects[0]?.id ?? localSessions[0]?.defects[0]?.id ?? null);
    setSynthetic(true);
    setNotice(null);
  }, []);

  const refreshSession = useCallback(async (id: string) => {
    const fresh = await api.session(id);
    setSessions((current) => current.map((item) => item.id === id ? fresh : item));
    return fresh;
  }, []);

  useEffect(() => {
    let alive = true;
    Promise.all([api.config(), api.demo(), loadLocalSessions().catch(() => [])]).then(async ([state, demo, localSessions]) => {
      if (!alive) return;
      setConfig(state);
      const combined = [...localSessions, ...demo.sessions];
      setSessions(combined);
      setActiveId(combined[0]?.id ?? null);
      setSelectedId(combined[0]?.defects[0]?.id ?? null);
      setSynthetic(localSessions.length === 0);
      if (state.real_processing_ready) {
        try {
          const saved = await api.sessions();
          if (alive && saved.length) {
            setSessions([...localSessions, ...saved]);
            setActiveId(saved[0].id);
            setSelectedId(saved[0].defects[0]?.id ?? null);
            setSynthetic(false);
            setNotice(null);
          }
        } catch {
          // Keep the synthetic presentation data available when the database is temporarily unreachable.
        }
      }
    }).catch((error: unknown) => {
      if (alive) setNotice({ text: error instanceof Error ? error.message : "No se pudo conectar con el backend.", kind: "error" });
    }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const activeSession = sessions.find((item) => item.id === activeId) ?? null;
  const allDefects = activeSession?.defects ?? [];
  const visibleDefects = allDefects.filter((item) => {
    return (typeFilter === "all" || item.defect_type === typeFilter)
      && (severityFilter === "all" || item.severity_estimated === severityFilter)
      && (statusFilter === "all" || item.review_status === statusFilter);
  });
  const selected = visibleDefects.find((item) => item.id === selectedId) ?? visibleDefects[0] ?? null;
  const selectedFrame = selected?.frame_id
    ? activeSession?.image_results?.find((frame) => frame.frame_id === selected.frame_id)
    : undefined;
  const selectedEvidenceUrl = selected?.evidence_url ?? selectedFrame?.evidence_url ?? null;

  const highCount = allDefects.filter((item) => item.severity_estimated === "high").length;
  const summary = activeSession?.analysis_summary;
  const conditions = ["good", "fair", "poor", "not_assessable"];

  async function submitVideo(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    if (!video && images.length === 0) return;
    const clearUploads = () => {
      form.querySelectorAll<HTMLInputElement>('input[type="file"]').forEach((input) => { input.value = ""; });
      setVideo(null);
      setImages([]);
      setGps(null);
    };
    setBusy(true);
    setNotice(null);
    try {
      if (!config?.real_processing_ready && config?.local_processing_ready) {
        const localSession = images.length > 0
          ? await api.analyzeLocalImages(name.trim() || "Secuencia de imágenes", images, gps ?? undefined)
          : await api.analyzeLocalVideo(name.trim() || video?.name || "Video de recorrido", video!, gps ?? undefined);
        await saveLocalSession(localSession);
        clearUploads();
        setSessions((current) => [localSession, ...current]);
        setActiveId(localSession.id);
        setSelectedId(localSession.defects[0]?.id ?? null);
        setSynthetic(false);
        setNotice({
          text: `Análisis local listo: ${localSession.analysis_summary?.frames_total ?? 0} fotogramas procesados, ${localSession.defects.length} detecciones. Se conserva en este navegador.`,
          kind: "success",
        });
        return;
      }
      const session = await api.createSession(name.trim() || video?.name || "Secuencia de imágenes");
      setSynthetic(false);
      setSessions((current) => [session, ...current]);
      setActiveId(session.id);
      setSelectedId(null);
      if (video) await api.upload(session.id, video, gps ?? undefined);
      else await api.uploadImages(session.id, images, gps ?? undefined);
      clearUploads();
      setNotice({ text: "Archivos recibidos. Se están procesando en segundo plano; el panel se actualizará al terminar.", kind: "success" });
      for (let attempt = 0; attempt < 90; attempt += 1) {
        await new Promise((resolve) => setTimeout(resolve, 2000));
        const fresh = await refreshSession(session.id);
        if (fresh.status === "completed") {
          setNotice({ text: `Análisis listo: ${fresh.defects.length} incidencias consolidadas.`, kind: "success" });
          setSelectedId(fresh.defects[0]?.id ?? null);
          return;
        }
        if (fresh.status === "failed") throw new Error(fresh.error_message || "No se pudo procesar el video.");
      }
      setNotice({ text: "El análisis continúa en segundo plano. Pulsa Actualizar para consultar el estado.", kind: "info" });
    } catch (error) {
      setNotice({ text: error instanceof Error ? error.message : "No se pudo enviar el recorrido.", kind: "error" });
    } finally {
      setBusy(false);
    }
  }

  async function refreshAll() {
    if (activeSession?.is_local) {
      try {
        const localSessions = await loadLocalSessions();
        setSessions((current) => [...localSessions, ...current.filter((item) => !item.is_local)]);
        const refreshed = localSessions.find((item) => item.id === activeId);
        if (refreshed) setSelectedId(refreshed.defects[0]?.id ?? null);
        setNotice({ text: refreshed ? "Análisis local actualizado desde este navegador." : "No se encontró el análisis local guardado.", kind: refreshed ? "success" : "info" });
      } catch (error) {
        setNotice({ text: error instanceof Error ? error.message : "No se pudo leer el almacenamiento local.", kind: "error" });
      }
      return;
    }
    if (synthetic) {
      await loadDemo();
      return;
    }
    try {
      const saved = await api.sessions();
      const localSessions = await loadLocalSessions().catch(() => []);
      setSessions([...localSessions, ...saved]);
      const current = saved.find((item) => item.id === activeId) ?? saved[0];
      if (current) {
        setActiveId(current.id);
        setSelectedId(current.defects[0]?.id ?? null);
      }
      setNotice({ text: "Datos actualizados desde el backend.", kind: "success" });
    } catch (error) {
      setNotice({ text: error instanceof Error ? error.message : "No se pudo actualizar.", kind: "error" });
    }
  }

  async function changeReviewStatus(defect: Defect, review_status: ReviewStatus) {
    if (defect.is_synthetic || defect.is_local) {
      const session = sessions.find((item) => item.id === defect.session_id);
      if (!session) return;
      const updatedSession = {
        ...session,
        defects: session.defects.map((item) => item.id === defect.id ? { ...item, review_status } : item),
      };
      try {
        if (updatedSession.is_local) await saveLocalSession(updatedSession);
        setSessions((current) => current.map((item) => item.id === session.id ? updatedSession : item));
        if (updatedSession.is_local) setNotice({ text: "Revisión local guardada en este navegador.", kind: "success" });
      } catch (error) {
        setNotice({ text: error instanceof Error ? error.message : "No se pudo guardar la revisión local.", kind: "error" });
      }
      return;
    }
    try {
      const updated = await api.updateDefect(defect.id, { review_status });
      setSessions((current) => current.map((session) => ({
        ...session,
        defects: session.defects.map((item) => item.id === defect.id ? updated : item),
      })));
    } catch (error) {
      setNotice({ text: error instanceof Error ? error.message : "No se pudo guardar la revisión.", kind: "error" });
    }
  }

  async function saveCorrection(defect: Defect, draft: CorrectionDraft) {
    const hasLatitude = draft.latitude.trim() !== "";
    const hasLongitude = draft.longitude.trim() !== "";
    if (hasLatitude !== hasLongitude) {
      setNotice({ text: "Para corregir la ubicación completa latitud y longitud.", kind: "error" });
      return;
    }
    const updates: Partial<Pick<Defect, "defect_type" | "severity_estimated" | "latitude" | "longitude">> = {
      defect_type: draft.defect_type,
      severity_estimated: draft.severity_estimated,
    };
    if (hasLatitude && hasLongitude) {
      const latitude = Number(draft.latitude);
      const longitude = Number(draft.longitude);
      if (!Number.isFinite(latitude) || !Number.isFinite(longitude) || latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
        setNotice({ text: "Revisa las coordenadas: latitud va de -90 a 90 y longitud de -180 a 180.", kind: "error" });
        return;
      }
      updates.latitude = latitude;
      updates.longitude = longitude;
    }
    if (defect.is_synthetic || defect.is_local) {
      const session = sessions.find((item) => item.id === defect.session_id);
      if (!session) return;
      const updatedSession = {
        ...session,
        defects: session.defects.map((item) => item.id === defect.id ? { ...item, ...updates } : item),
      };
      try {
        if (updatedSession.is_local) await saveLocalSession(updatedSession);
        setSessions((current) => current.map((item) => item.id === session.id ? updatedSession : item));
        setNotice({ text: defect.is_local ? "Corrección aplicada a este análisis local del navegador." : "Cambios aplicados solo a esta demostración sintética.", kind: "info" });
      } catch (error) {
        setNotice({ text: error instanceof Error ? error.message : "No se pudo guardar la corrección local.", kind: "error" });
      }
      return;
    }
    try {
      const updated = await api.updateDefect(defect.id, updates);
      setSessions((current) => current.map((session) => ({
        ...session,
        defects: session.defects.map((item) => item.id === defect.id ? updated : item),
      })));
      setNotice({ text: "Corrección guardada.", kind: "success" });
    } catch (error) {
      setNotice({ text: error instanceof Error ? error.message : "No se pudo guardar la corrección.", kind: "error" });
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><Road size={19} strokeWidth={2.3} /></div><span>VialScan</span></div>
        <div className="topbar-right">
          <div className="system-state"><span className={`status-dot ${synthetic || activeSession?.is_local ? "demo" : ""}`} /><span className="system-label">{activeSession?.is_local ? "Análisis local" : synthetic ? "Modo demostración" : "Datos del recorrido"}</span></div>
          <button className="button" onClick={refreshAll} aria-label="Actualizar"><RefreshCw size={14} />Actualizar</button>
        </div>
      </header>

      <div className="page-wrap">
        <section className="page-heading">
          <div>
            <div className="eyebrow">Monitoreo de infraestructura vial</div>
            <h1>Estado de calles</h1>
            <p className="subtitle">Un recorrido, evidencia ordenada y señales claras para priorizar qué revisar primero.</p>
          </div>
          <div className="heading-actions">
            <select className="select" value={activeId ?? ""} onChange={(event) => {
              const next = sessions.find((item) => item.id === event.target.value);
              setActiveId(event.target.value || null);
              setSelectedId(next?.defects[0]?.id ?? null);
              setSynthetic(next?.defects.some((item) => item.is_synthetic) ?? false);
            }} aria-label="Seleccionar recorrido">
              {sessions.map((item) => <option value={item.id} key={item.id}>{item.name} · {STATUS_COPY[item.status] ?? item.status}</option>)}
              {!sessions.length && <option value="">Sin recorridos</option>}
            </select>
            {synthetic && <button className="button" onClick={() => void loadDemo()}><Sparkles size={14} />Cargar demo</button>}
          </div>
        </section>

        <section className="metrics" aria-label="Resumen del recorrido">
          <Metric label="Fotogramas analizados" value={summary?.frames_total ?? "—"} icon={<Activity size={17} />} />
          <Metric label="Buen estado visible" value={summary ? `${summary.condition_percentages?.good ?? 0}%` : "—"} icon={<Road size={17} />} />
          <Metric label="Incidencias agrupadas" value={summary?.consolidated_incidents ?? allDefects.length} icon={<AlertTriangle size={17} />} iconClass="warn" />
          <Metric label="Prioridad alta" value={highCount} icon={<Clock3 size={17} />} iconClass="alert" />
        </section>

        <section className="panel condition-panel" aria-label="Distribución del estado visual">
          <div className="condition-heading"><div><div className="panel-title">Evaluación visual del recorrido</div><div className="panel-caption">Distribución de los fotogramas muestreados; no certifica el estado de toda la calle</div></div><span className="chip">{summary?.frames_total ?? 0} cuadros</span></div>
          <div className="condition-grid">
            {conditions.map((condition) => {
              const percentage = summary?.condition_percentages?.[condition] ?? 0;
              const count = summary?.condition_counts?.[condition] ?? 0;
              return <div className="condition-item" key={condition}>
                <div className="condition-label"><span><i className="legend-dot" style={{ background: CONDITION_COLORS[condition] }} />{CONDITION_LABELS[condition]}</span><strong>{count} <small>({percentage}%)</small></strong></div>
                <div className="condition-track"><div className="condition-fill" style={{ width: `${Math.max(0, Math.min(100, percentage))}%`, background: CONDITION_COLORS[condition] }} /></div>
              </div>;
            })}
          </div>
        </section>

        {activeSession?.image_results?.length ? <section className="panel frame-gallery-panel">
          <div className="panel-head"><div><div className="panel-title">Fotogramas analizados</div><div className="panel-caption">Evidencia de todas las imágenes, incluso las que no tuvieron detecciones</div></div><span className="chip">{activeSession.image_results.length} imágenes</span></div>
          <div className="frame-gallery">{activeSession.image_results.map((frame) => {
            const frameDefect = activeSession.defects.find((item) => item.frame_id === frame.frame_id);
            return <button type="button" className="frame-card" key={frame.frame_id} onClick={() => setSelectedId(frameDefect?.id ?? null)}>
              <Image src={frame.evidence_url} alt={`Fotograma ${frame.file_name}`} width={320} height={200} unoptimized loading="lazy" />
              <span className="frame-card-name" title={frame.file_name}>{frame.file_name}</span>
              <span className="frame-card-meta">{CONDITION_LABELS[frame.road_condition]} · {frame.defect_count} {frame.defect_count === 1 ? "detección" : "detecciones"}</span>
            </button>;
          })}</div>
        </section> : null}

        <section className="workspace-grid">
          <div className="panel map-panel">
            <div className="panel-head">
              <div><div className="panel-title">Recorrido y observaciones</div><div className="panel-caption">El trazo resume el estado por fotograma; los círculos grandes marcan incidencias</div></div>
              {activeSession && <span className={`chip ${activeSession.status === "completed" ? "confirmed" : ""}`}>{STATUS_COPY[activeSession.status] ?? activeSession.status}</span>}
            </div>
            <div className="map-shell">
              {loading ? <div className="map-canvas grid place-items-center text-sm text-slate-500">Preparando mapa…</div>
                : <RoadMap defects={visibleDefects} conditionPoints={activeSession?.condition_points ?? []} routeSegments={activeSession?.route_segments ?? []} selectedId={selected?.id ?? null} onSelect={setSelectedId} />}
              {synthetic && <div className="map-label">RECORRIDO SINTÉTICO · MENDOZA</div>}
              <div className="map-legend">
                <span className="legend-item"><i className="legend-dot" style={{ background: CONDITION_COLORS.good }} />Buen estado</span>
                <span className="legend-item"><i className="legend-dot" style={{ background: CONDITION_COLORS.fair }} />Leve</span>
                <span className="legend-item"><i className="legend-dot" style={{ background: CONDITION_COLORS.poor }} />Deteriorado</span>
                <span className="legend-item"><i className="legend-dot" style={{ background: CONDITION_COLORS.not_assessable }} />No evaluable</span>
                <span className="legend-item">Círculo grande: incidencia</span>
              </div>
            </div>
          </div>

          <aside className="panel list-panel">
            <div className="panel-head">
              <div><div className="panel-title">Incidencias</div><div className="panel-caption">Selecciona una para ver evidencia y revisar</div></div>
              <div className="filters">
                <select className="select" value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filtrar por tipo">
                  <option value="all">Todos los tipos</option>
                  {Object.entries(TYPE_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
                <select className="select" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} aria-label="Filtrar por severidad">
                  <option value="all">Severidad</option>
                  {Object.entries(SEVERITY_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
                </select>
              </div>
            </div>
            <div className="filters px-4 py-2 border-b border-slate-100">
              <select className="select" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filtrar por estado">
                <option value="all">Todos los estados</option>
                {Object.entries(STATUS_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
              </select>
              <span className="text-[10px] text-slate-500 self-center">{visibleDefects.length} resultados</span>
            </div>
            <div className="defect-list">
              {visibleDefects.length ? visibleDefects.map((item) => (
                <button key={item.id} className={`defect-row w-full text-left ${selected?.id === item.id ? "selected" : ""}`} onClick={() => setSelectedId(item.id)}>
                  <span className={`defect-icon ${item.severity_estimated}`}><AlertTriangle size={15} /></span>
                  <span className="defect-main">
                    <span className="defect-title-line"><span className="defect-name">{TYPE_LABELS[item.defect_type] ?? item.defect_type}</span><span className="defect-time">{formatTime(item.first_observed_at)}</span></span>
                    <span className="defect-description line-clamp-2">{item.description}</span>
                    <span className="chips">
                      <span className={`chip ${item.severity_estimated}`}>{SEVERITY_LABELS[item.severity_estimated]}</span>
                      <span className={`chip ${item.review_status === "confirmed" ? "confirmed" : ""}`}>{STATUS_LABELS[item.review_status]}</span>
                      {item.is_synthetic && <span className="chip synthetic">Sintético</span>}
                      {item.is_local && <span className="chip local">Detector local</span>}
                    </span>
                  </span>
                  <ArrowUpRight size={14} className="mt-1 text-slate-400" />
                </button>
              )) : <div className="empty-state">{loading ? "Cargando observaciones…" : "No hay incidencias con estos filtros."}</div>}
            </div>
            {selected && <div className="detail">
              <div className="detail-top"><div className="detail-title">Detalle de observación</div><span className="chip">{Math.round(selected.confidence * 100)}% confianza visual</span></div>
              {selectedEvidenceUrl ? <Image className="evidence" src={selectedEvidenceUrl} alt={selected.is_synthetic ? "Foto pública de referencia" : "Fotograma usado como evidencia"} width={960} height={480} unoptimized /> : (
                <div className="rounded-lg border border-dashed border-slate-200 bg-white p-3 text-[10px] leading-5 text-slate-500">{selected.is_synthetic ? "Evidencia ilustrativa no adjunta en esta demo." : "No hay imagen de evidencia disponible."}</div>
              )}
              {selected.is_synthetic && selected.evidence_url && <p className="text-[9px] leading-4 text-slate-500 mt-1">Foto de referencia pública{selected.evidence_source_url && selected.evidence_credit ? <> · <a href={selected.evidence_source_url} target="_blank" rel="noreferrer" className="underline">{selected.evidence_credit}</a></> : null}. La clasificación es sintética; esta foto no se analizó en vivo.</p>}
              <p className="text-[11px] leading-5 text-slate-600 mt-2">{selected.description}</p>
              <div className="detail-meta">
                <div><span>Ubicación</span><strong>{selected.latitude !== null ? `${selected.latitude.toFixed(5)}, ${selected.longitude?.toFixed(5)}` : "Sin georreferenciar"}</strong></div>
                <div><span>Severidad estimada</span><strong>{SEVERITY_LABELS[selected.severity_estimated]}</strong></div>
                <div><span>Observada</span><strong>{formatTime(selected.first_observed_at)}</strong></div>
              </div>
              <CorrectionEditor
                key={`${selected.id}:${selected.defect_type}:${selected.severity_estimated}:${selected.latitude}:${selected.longitude}`}
                defect={selected}
                onSave={saveCorrection}
                onReviewStatus={changeReviewStatus}
              />
            </div>}
          </aside>
        </section>

        <form className="panel upload-panel" onSubmit={submitVideo}>
          <div>
            <div className="upload-copy"><span className="upload-icon"><CloudUpload size={19} /></span><span><span className="upload-title">Analizar un nuevo recorrido</span><span className="upload-text block">Carga un video corto o una secuencia de imágenes, y opcionalmente el track GPS GPX/CSV.</span></span></div>
            {notice && <div className={`notice ${notice.kind === "error" ? "error" : notice.kind === "success" ? "success" : ""}`}>{notice.text}</div>}
            {activeSession?.status === "failed" && activeSession.error_message && <div className="notice error">{activeSession.error_message}</div>}
          </div>
          <div className="upload-controls">
            <input className="select w-[150px]" value={name} onChange={(event) => setName(event.target.value)} aria-label="Nombre del recorrido" />
            <label className="file-input"><FileVideo2 size={14} className="inline mr-1" /><input type="file" accept="video/*,.mp4,.mov,.avi,.webm,.m4v" onChange={(event) => { setVideo(event.target.files?.[0] ?? null); setImages([]); }} /></label>
            <label className="file-input"><Sparkles size={14} className="inline mr-1" /><input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => { setImages(Array.from(event.target.files ?? [])); setVideo(null); }} /></label>
            <label className="file-input"><MapPin size={14} className="inline mr-1" /><input type="file" accept=".gpx,.csv" onChange={(event) => setGps(event.target.files?.[0] ?? null)} /></label>
            <button className="button primary" type="submit" disabled={(!config?.real_processing_ready && !config?.local_processing_ready) || (!video && images.length === 0) || busy}>
              {busy ? <><LoaderCircle size={14} className="spin" />Procesando</> : <><Sparkles size={14} />{!config?.real_processing_ready ? "Analizar localmente" : "Analizar"}</>}
            </button>
          </div>
        </form>

        <p className="mt-3 px-1 text-[10px] leading-5 text-slate-500"><ShieldCheck size={12} className="inline mr-1" />La severidad y la ubicación son estimaciones para revisión humana. La cámara monocular no permite conocer profundidad ni dimensiones reales.</p>
      </div>
    </main>
  );
}

function Metric({ label, value, icon, iconClass = "" }: { label: string; value: string | number; icon: React.ReactNode; iconClass?: string }) {
  return <div className="metric-card"><div><div className="metric-label">{label}</div><div className="metric-value">{value}</div></div><div className={`metric-icon ${iconClass}`}>{icon}</div></div>;
}

interface CorrectionDraft {
  defect_type: DefectType;
  severity_estimated: Severity;
  latitude: string;
  longitude: string;
}

function CorrectionEditor({ defect, onSave, onReviewStatus }: {
  defect: Defect;
  onSave: (defect: Defect, draft: CorrectionDraft) => Promise<void>;
  onReviewStatus: (defect: Defect, status: ReviewStatus) => Promise<void>;
}) {
  const [defectType, setDefectType] = useState<DefectType>(defect.defect_type);
  const [severity, setSeverity] = useState<Severity>(defect.severity_estimated);
  const [latitude, setLatitude] = useState(defect.latitude === null ? "" : String(defect.latitude));
  const [longitude, setLongitude] = useState(defect.longitude === null ? "" : String(defect.longitude));

  return <>
    <div className="correction-grid">
      <label>Tipo
        <select className="select" value={defectType} onChange={(event) => setDefectType(event.target.value as DefectType)}>
          {Object.entries(TYPE_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label>Severidad
        <select className="select" value={severity} onChange={(event) => setSeverity(event.target.value as Severity)}>
          {Object.entries(SEVERITY_LABELS).map(([value, label]) => <option value={value} key={value}>{label}</option>)}
        </select>
      </label>
      <label>Latitud
        <input className="select" inputMode="decimal" value={latitude} onChange={(event) => setLatitude(event.target.value)} placeholder="-32.89" />
      </label>
      <label>Longitud
        <input className="select" inputMode="decimal" value={longitude} onChange={(event) => setLongitude(event.target.value)} placeholder="-68.84" />
      </label>
    </div>
    <div className="detail-actions">
      <button className="button" onClick={() => void onSave(defect, { defect_type: defectType, severity_estimated: severity, latitude, longitude })}><Check size={13} />Guardar corrección</button>
      <button className="button primary" onClick={() => void onReviewStatus(defect, "confirmed")}><Check size={13} />Confirmar</button>
      <button className="button" onClick={() => void onReviewStatus(defect, "dismissed")}><X size={13} />Descartar</button>
    </div>
  </>;
}
