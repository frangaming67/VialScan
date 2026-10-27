"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, ArrowUpRight, Check, Clock3, CloudUpload, FileVideo2,
  LoaderCircle, MapPin, RefreshCw, Road, ShieldCheck, Sparkles, X,
} from "lucide-react";
import { api } from "@/lib/api";
import type { ConfigStatus, Defect, ReviewStatus, ScanSession, Severity } from "@/lib/types";

const RoadMap = dynamic(() => import("@/components/road-map"), {
  ssr: false,
  loading: () => <div className="map-shell grid place-items-center text-sm text-slate-500">Cargando mapa…</div>,
});

const TYPE_LABELS: Record<string, string> = {
  pothole: "Pozo / bache", crack: "Grieta", patch: "Parche", deformation: "Deformación", other: "Otro",
};
const SEVERITY_LABELS: Record<Severity, string> = { low: "Baja", medium: "Media", high: "Alta", unknown: "Sin estimar" };
const STATUS_LABELS: Record<ReviewStatus, string> = { pending: "Pendiente", confirmed: "Confirmado", dismissed: "Descartado" };
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
    const demo = await api.demo();
    setSessions(demo.sessions);
    setActiveId(demo.sessions[0]?.id ?? null);
    setSelectedId(demo.sessions[0]?.defects[0]?.id ?? null);
    setSynthetic(true);
    setNotice({ text: demo.message, kind: "info" });
  }, []);

  const refreshSession = useCallback(async (id: string) => {
    const fresh = await api.session(id);
    setSessions((current) => current.map((item) => item.id === id ? fresh : item));
    return fresh;
  }, []);

  useEffect(() => {
    let alive = true;
    Promise.all([api.config(), api.demo()]).then(async ([state, demo]) => {
      if (!alive) return;
      setConfig(state);
      setSessions(demo.sessions);
      setActiveId(demo.sessions[0]?.id ?? null);
      setSelectedId(demo.sessions[0]?.defects[0]?.id ?? null);
      setNotice({ text: demo.message, kind: "info" });
      if (state.real_processing_ready) {
        try {
          const saved = await api.sessions();
          if (alive && saved.length) {
            setSessions(saved);
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
  const visibleDefects = useMemo(() => allDefects.filter((item) => {
    return (typeFilter === "all" || item.defect_type === typeFilter)
      && (severityFilter === "all" || item.severity_estimated === severityFilter)
      && (statusFilter === "all" || item.review_status === statusFilter);
  }), [allDefects, typeFilter, severityFilter, statusFilter]);
  const selected = allDefects.find((item) => item.id === selectedId) ?? visibleDefects[0] ?? null;
  const pendingCount = allDefects.filter((item) => item.review_status === "pending").length;
  const highCount = allDefects.filter((item) => item.severity_estimated === "high").length;
  const georeferencedCount = allDefects.filter((item) => item.latitude !== null && item.longitude !== null).length;

  async function submitVideo(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!video && images.length === 0) return;
    setBusy(true);
    setNotice(null);
    try {
      const session = await api.createSession(name.trim() || video?.name || "Secuencia de imágenes");
      setSynthetic(false);
      setSessions((current) => [session, ...current]);
      setActiveId(session.id);
      setSelectedId(null);
      if (video) await api.upload(session.id, video, gps ?? undefined);
      else await api.uploadImages(session.id, images, gps ?? undefined);
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
    if (synthetic) {
      await loadDemo();
      return;
    }
    try {
      const saved = await api.sessions();
      setSessions(saved);
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
    if (defect.is_synthetic) {
      setSessions((current) => current.map((session) => ({
        ...session,
        defects: session.defects.map((item) => item.id === defect.id ? { ...item, review_status } : item),
      })));
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

  return (
    <main className="app-shell">
      <header className="topbar">
        <div className="brand"><div className="brand-mark"><Road size={19} strokeWidth={2.3} /></div><span>VialScan</span></div>
        <div className="topbar-right">
          <div className="system-state"><span className={`status-dot ${synthetic ? "demo" : ""}`} /><span className="system-label">{synthetic ? "Modo demostración" : "Datos del recorrido"}</span></div>
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
          <Metric label="Incidencias detectadas" value={allDefects.length} icon={<Activity size={17} />} />
          <Metric label="Requieren revisión" value={pendingCount} icon={<Clock3 size={17} />} iconClass="warn" />
          <Metric label="Prioridad alta" value={highCount} icon={<AlertTriangle size={17} />} iconClass="alert" />
          <Metric label="Con ubicación" value={`${georeferencedCount}/${allDefects.length}`} icon={<MapPin size={17} />} />
        </section>

        <section className="workspace-grid">
          <div className="panel">
            <div className="panel-head">
              <div><div className="panel-title">Recorrido y observaciones</div><div className="panel-caption">Los puntos muestran ubicaciones aproximadas asociadas al video</div></div>
              {activeSession && <span className={`chip ${activeSession.status === "completed" ? "confirmed" : ""}`}>{STATUS_COPY[activeSession.status] ?? activeSession.status}</span>}
            </div>
            <div className="map-shell">
              {loading ? <div className="map-canvas grid place-items-center text-sm text-slate-500">Preparando mapa…</div>
                : <RoadMap defects={visibleDefects} selectedId={selected?.id ?? null} onSelect={setSelectedId} />}
              {synthetic && <div className="map-label">RECORRIDO SINTÉTICO · UBICACIONES DE EJEMPLO</div>}
              <div className="map-legend">
                <span className="legend-item"><i className="legend-dot" style={{ background: "#e15d4f" }} />Alta</span>
                <span className="legend-item"><i className="legend-dot" style={{ background: "#e9a23b" }} />Media</span>
                <span className="legend-item"><i className="legend-dot" style={{ background: "#45a67b" }} />Baja</span>
                <span className="legend-item"><i className="legend-dot" style={{ background: "#728096" }} />Sin estimar</span>
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
                    </span>
                  </span>
                  <ArrowUpRight size={14} className="mt-1 text-slate-400" />
                </button>
              )) : <div className="empty-state">{loading ? "Cargando observaciones…" : "No hay incidencias con estos filtros."}</div>}
            </div>
            {selected && <div className="detail">
              <div className="detail-top"><div className="detail-title">Detalle de observación</div><span className="chip">{Math.round(selected.confidence * 100)}% confianza visual</span></div>
              {selected.evidence_url ? <img className="evidence" src={selected.evidence_url} alt="Fotograma usado como evidencia" /> : (
                <div className="rounded-lg border border-dashed border-slate-200 bg-white p-3 text-[10px] leading-5 text-slate-500">{selected.is_synthetic ? "Evidencia ilustrativa no adjunta en esta demo." : "No hay imagen de evidencia disponible."}</div>
              )}
              <p className="text-[11px] leading-5 text-slate-600 mt-2">{selected.description}</p>
              <div className="detail-meta">
                <div><span>Ubicación</span><strong>{selected.latitude !== null ? `${selected.latitude.toFixed(5)}, ${selected.longitude?.toFixed(5)}` : "Sin georreferenciar"}</strong></div>
                <div><span>Severidad estimada</span><strong>{SEVERITY_LABELS[selected.severity_estimated]}</strong></div>
                <div><span>Observada</span><strong>{formatTime(selected.first_observed_at)}</strong></div>
              </div>
              <div className="detail-actions">
                <button className="button primary" onClick={() => void changeReviewStatus(selected, "confirmed")}><Check size={13} />Confirmar</button>
                <button className="button" onClick={() => void changeReviewStatus(selected, "dismissed")}><X size={13} />Descartar</button>
              </div>
            </div>}
          </aside>
        </section>

        <form className="panel upload-panel" onSubmit={submitVideo}>
          <div>
            <div className="upload-copy"><span className="upload-icon"><CloudUpload size={19} /></span><span><span className="upload-title">Analizar un nuevo recorrido</span><span className="upload-text block">Carga un video corto o una secuencia de imágenes, y opcionalmente el track GPS GPX/CSV.</span></span></div>
            {notice && <div className={`notice ${notice.kind === "error" ? "error" : notice.kind === "success" ? "success" : ""}`}>{notice.text}</div>}
            {config && !config.real_processing_ready && <div className="notice">Para procesar videos reales faltan: {config.missing_variables.join(", ")}. Puedes recorrer la interfaz en modo sintético.</div>}
            {activeSession?.status === "failed" && activeSession.error_message && <div className="notice error">{activeSession.error_message}</div>}
          </div>
          <div className="upload-controls">
            <input className="select w-[150px]" value={name} onChange={(event) => setName(event.target.value)} aria-label="Nombre del recorrido" />
            <label className="file-input"><FileVideo2 size={14} className="inline mr-1" /><input type="file" accept="video/*,.mp4,.mov,.avi,.webm,.m4v" onChange={(event) => { setVideo(event.target.files?.[0] ?? null); setImages([]); }} /></label>
            <label className="file-input"><Sparkles size={14} className="inline mr-1" /><input type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => { setImages(Array.from(event.target.files ?? [])); setVideo(null); }} /></label>
            <label className="file-input"><MapPin size={14} className="inline mr-1" /><input type="file" accept=".gpx,.csv" onChange={(event) => setGps(event.target.files?.[0] ?? null)} /></label>
            <button className="button primary" type="submit" disabled={!config?.real_processing_ready || (!video && images.length === 0) || busy}>
              {busy ? <><LoaderCircle size={14} className="spin" />Procesando</> : <><Sparkles size={14} />Analizar</>}
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
