import { useCallback, useEffect, useRef, useState, type PointerEvent } from 'react';

type Region = { x: number; y: number; width: number; height: number };
type Annotation = { id: string; seconds: number; kind: 'observation' | 'arrival' | 'movement' | 'removal' | 'visibility_gap'; note: string; source: 'manual' };
type Review = { region: Region | null; start_seconds: number | null; end_seconds: number | null; notes: string; annotations: Annotation[] };
type Session = { id: string; filename: string; created_at: string; video_url: string; review: Review };

const kinds: { value: Annotation['kind']; label: string }[] = [
  { value: 'observation', label: 'Observation' }, { value: 'arrival', label: 'New arrival' },
  { value: 'movement', label: 'Movement' }, { value: 'removal', label: 'Removal' },
  { value: 'visibility_gap', label: 'View blocked' },
];

function time(seconds: number | null) {
  if (seconds === null) return 'Not marked';
  return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
}

function message(error: unknown) { return error instanceof Error ? error.message : 'Something went wrong'; }

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const body = await response.json(); detail = typeof body.detail === 'string' ? body.detail : detail; } catch { /* no JSON error */ }
    throw new Error(detail);
  }
  return response.json();
}

export default function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [active, setActive] = useState<Session | null>(null);
  const [review, setReview] = useState<Review | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [drawing, setDrawing] = useState(false);
  const [draftRegion, setDraftRegion] = useState<Region | null>(null);
  const [note, setNote] = useState('');
  const [kind, setKind] = useState<Annotation['kind']>('observation');
  const [dirty, setDirty] = useState(false);
  const video = useRef<HTMLVideoElement>(null);
  const surface = useRef<HTMLDivElement>(null);
  const start = useRef<{ x: number; y: number } | null>(null);

  const select = useCallback((item: Session) => {
    setActive(item); setReview(structuredClone(item.review)); setDraftRegion(null);
    setDirty(false); setStatus(''); setError(''); setDrawing(false);
  }, []);

  useEffect(() => {
    api<Session[]>('/api/sessions').then(items => { setSessions(items); if (items[0]) select(items[0]); }).catch(e => setError(message(e)));
  }, [select]);

  function change(next: Review) { setReview(next); setDirty(true); setStatus(''); }

  async function upload(file?: File) {
    if (!file) return;
    setError(''); setBusy(true); setStatus('Uploading video…');
    try {
      const body = new FormData(); body.append('video', file);
      const created = await api<Session>('/api/sessions', { method: 'POST', body });
      setSessions(current => [created, ...current]); select(created); setStatus('Video uploaded. Mark the area you want to review.');
    } catch (e) { setError(message(e)); setStatus(''); }
    finally { setBusy(false); }
  }

  async function save() {
    if (!active || !review) return;
    setBusy(true); setError('');
    try {
      const updated = await api<Session>(`/api/sessions/${active.id}/review`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(review),
      });
      setActive(updated); setReview(structuredClone(updated.review));
      setSessions(items => items.map(item => item.id === updated.id ? updated : item));
      setDirty(false); setStatus('Review saved on this computer.');
    } catch (e) { setError(message(e)); }
    finally { setBusy(false); }
  }

  function point(event: PointerEvent<HTMLDivElement>) {
    const box = surface.current!.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)), y: Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)) };
  }

  function move(event: PointerEvent<HTMLDivElement>) {
    if (!start.current) return;
    const end = point(event), begin = start.current;
    setDraftRegion({ x: Math.min(begin.x, end.x), y: Math.min(begin.y, end.y), width: Math.abs(end.x - begin.x), height: Math.abs(end.y - begin.y) });
  }

  function finish(event: PointerEvent<HTMLDivElement>) {
    if (!start.current || !review) return;
    move(event);
    const end = point(event), begin = start.current;
    const next = { x: Math.min(begin.x, end.x), y: Math.min(begin.y, end.y), width: Math.abs(end.x - begin.x), height: Math.abs(end.y - begin.y) };
    if (next.width > 0.01 && next.height > 0.01) change({ ...review, region: next });
    start.current = null; setDraftRegion(null); setDrawing(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
  }

  function addAnnotation() {
    if (!review || !note.trim() || !video.current) return;
    change({ ...review, annotations: [...review.annotations, { id: crypto.randomUUID(), seconds: video.current.currentTime, kind, note: note.trim(), source: 'manual' }] });
    setNote('');
  }

  const region = draftRegion ?? review?.region;
  const ordered = [...(review?.annotations ?? [])].sort((a, b) => a.seconds - b.seconds);

  return <div className="app">
    <aside className="sidebar">
      <div className="brand"><span className="mark">G</span><span>GLENWAKE<small>VIDEO REVIEW STUDIO</small></span></div>
      <div className="sidebar-section"><div className="eyebrow">WORKSPACE / 01</div><h2>Sessions</h2><p>Each recording keeps its own review notes and cleanup window.</p></div>
      <label className={`upload ${busy ? 'disabled' : ''}`}><span>＋</span> New recording<input type="file" accept=".mp4,.webm,.mov,video/mp4,video/webm,video/quicktime" disabled={busy} onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }} /></label>
      <div className="session-list">{sessions.map(item => <button key={item.id} className={`session ${active?.id === item.id ? 'selected' : ''}`} onClick={() => { if (dirty && !window.confirm('Discard unsaved review changes?')) return; select(item); }}><span className="session-icon">▶</span><span className="session-text"><strong title={item.filename}>{item.filename}</strong><small>{item.created_at.slice(0, 10)} · {item.review.annotations.length} notes</small></span></button>)}{!sessions.length && <div className="empty-list">No recordings yet.<br />Upload one to begin.</div>}</div>
      <div className="sidebar-foot">LOCAL WORKSPACE <span className="online-dot" /> <br /><small>Original recordings stay on this computer.</small></div>
    </aside>
    <main>
      <header className="topbar"><span>REVIEW / {active ? active.filename : 'NEW SESSION'}</span><span className="manual-chip">● MANUAL REVIEW</span></header>
      {error && <div role="alert" className="error">{error}</div>}
      {!active || !review ? <section className="welcome"><div className="welcome-symbol">◌</div><div className="eyebrow">A CLEARER RECORD OF CLEANUP</div><h1>See what changed.<br /><em>Keep the evidence.</em></h1><p>Start with a stationary-camera recording. Draw the area of interest, mark when cleanup began and ended, then annotate what you can actually see.</p><label className="primary-upload">Upload your first video<input type="file" accept=".mp4,.webm,.mov" onChange={e => { void upload(e.target.files?.[0]); e.target.value = ''; }} /></label></section> : <div className="workspace">
        <div className="heading"><div><div className="eyebrow">SESSION / RECORDING</div><h1>{active.filename}</h1><p>Review visible events and save your observations.</p></div><button className="save" disabled={busy || !dirty} onClick={() => void save()}>{busy ? 'Working…' : dirty ? 'Save review' : 'Saved ✓'}</button></div>
        <div className="grid"><div className="left-column"><section className="card player-card"><div className="card-head"><span>01 / RECORDING</span><span>ORIGINAL VIDEO</span></div><div ref={surface} className={`video-surface ${drawing ? 'draw-mode' : ''}`} onPointerDown={e => { if (!drawing) return; start.current = point(e); e.currentTarget.setPointerCapture(e.pointerId); }} onPointerMove={move} onPointerUp={finish} onPointerCancel={e => { start.current = null; setDraftRegion(null); setDrawing(false); if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId); }}><video ref={video} key={active.id} controls playsInline src={active.video_url} />{region && <div className="region" style={{ left: `${region.x * 100}%`, top: `${region.y * 100}%`, width: `${region.width * 100}%`, height: `${region.height * 100}%` }}><span>MONITORING AREA</span></div>}{drawing && <div className="draw-hint">Drag across the video to mark the area</div>}</div><div className="player-actions"><button className={drawing ? 'active-button' : ''} onClick={() => { video.current?.pause(); setDrawing(!drawing); }}>{drawing ? 'Cancel drawing' : review.region ? 'Redraw monitoring area' : 'Draw monitoring area'}</button><span>{review.region ? 'Area selected' : 'No area selected'}</span></div></section>
          <section className="card timeline"><div className="card-head"><span>02 / EVENT LOG</span><span>{ordered.length} ENTRIES</span></div><div className="timeline-title"><h2>What happened?</h2><p>Pause at a useful moment, record the observation, and return to it later.</p></div><div className="event-form"><select aria-label="Event type" value={kind} onChange={e => setKind(e.target.value as Annotation['kind'])}>{kinds.map(k => <option key={k.value} value={k.value}>{k.label}</option>)}</select><input aria-label="Observation" placeholder="Describe what is visible in the frame…" value={note} onChange={e => setNote(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') addAnnotation(); }} /><button disabled={!note.trim()} onClick={addAnnotation}>Add at playhead</button></div><div className="events">{ordered.map(event => <div className="event" key={event.id}><button className="event-time" onClick={() => { if (video.current) { video.current.currentTime = event.seconds; video.current.pause(); } }}>{time(event.seconds)}</button><div><strong>{kinds.find(k => k.value === event.kind)?.label}</strong><p>{event.note}</p><small>MANUAL OBSERVATION</small></div><button aria-label="Remove observation" className="remove" onClick={() => change({ ...review, annotations: review.annotations.filter(a => a.id !== event.id) })}>×</button></div>)}{!ordered.length && <div className="empty-events">Your observations will appear here. Nothing has been inferred from this recording.</div>}</div></section></div>
          <div className="right-column"><section className="card"><div className="card-head"><span>03 / CLEANUP WINDOW</span><span>TIME MARKERS</span></div><div className="panel-body"><h2>Set the boundaries</h2><p>Play or seek to the start and end of cleanup, then mark each point.</p><div className="marker"><div><small>START</small><strong>{time(review.start_seconds)}</strong></div><button onClick={() => change({ ...review, start_seconds: video.current?.currentTime ?? 0 })}>Mark current time</button></div><div className="marker"><div><small>END</small><strong>{time(review.end_seconds)}</strong></div><button onClick={() => change({ ...review, end_seconds: video.current?.currentTime ?? 0 })}>Mark current time</button></div>{review.start_seconds !== null && review.end_seconds !== null && review.end_seconds <= review.start_seconds && <p className="validation">End must be after start before saving.</p>}</div></section><section className="card notes-card"><div className="card-head"><span>04 / REVIEW NOTES</span><span>HUMAN INPUT</span></div><div className="panel-body"><h2>Reviewer notes</h2><p>Record conditions, uncertainty or context the video alone cannot settle.</p><textarea aria-label="Reviewer notes" placeholder="Example: A truck blocks the area between 01:20 and 01:45. The object's origin remains unclear." value={review.notes} onChange={e => change({ ...review, notes: e.target.value })} /><div className="note-caption">These notes are yours. GlenWake has not analyzed the video automatically.</div></div></section><div className="guide"><span>REVIEW CHECKLIST</span><p>① Draw the fixed monitoring area<br />② Mark cleanup start and end<br />③ Add timestamped observations<br />④ Save and reopen the session</p></div></div></div>
        {status && <div role="status" className="status">{status}</div>}
      </div>}
    </main>
  </div>;
}
