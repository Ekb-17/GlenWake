import { useCallback, useEffect, useRef, useState, type PointerEvent } from 'react';

type Region = { x: number; y: number; width: number; height: number };
type Annotation = { id: string; seconds: number; kind: 'observation' | 'arrival' | 'movement' | 'removal' | 'visibility_gap'; note: string; source: 'manual' };
type Review = { region: Region | null; start_seconds: number | null; end_seconds: number | null; notes: string; annotations: Annotation[] };
type Session = { id: string; filename: string; created_at: string; video_url: string; review: Review };

const VIDEO_ACCEPT = '.mp4,.webm,.mov,video/mp4,video/webm,video/quicktime';

const kinds: { value: Annotation['kind']; label: string }[] = [
  { value: 'observation', label: 'Observation' },
  { value: 'arrival', label: 'New arrival' },
  { value: 'movement', label: 'Movement' },
  { value: 'removal', label: 'Removal' },
  { value: 'visibility_gap', label: 'View blocked' },
];

function time(seconds: number | null) {
  if (seconds === null) return 'Not marked';
  return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
}

function message(error: unknown) {
  return error instanceof Error ? error.message : 'Something went wrong';
}

async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      detail = typeof body.detail === 'string' ? body.detail : detail;
    } catch {
      /* no JSON error */
    }
    throw new Error(detail);
  }
  return response.json();
}

function sessionMeta(item: Session) {
  const notes = item.review.annotations.length;
  const area = item.review.region ? 'area marked' : 'no area';
  return `${item.created_at.slice(0, 10)} · ${notes} ${notes === 1 ? 'observation' : 'observations'} · ${area}`;
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
    setActive(item);
    setReview(structuredClone(item.review));
    setDraftRegion(null);
    setDirty(false);
    setStatus('');
    setError('');
    setDrawing(false);
  }, []);

  useEffect(() => {
    api<Session[]>('/api/sessions')
      .then(items => {
        setSessions(items);
        if (items[0]) select(items[0]);
      })
      .catch(e => setError(message(e)));
  }, [select]);

  function change(next: Review) {
    setReview(next);
    setDirty(true);
    setStatus('');
  }

  async function upload(file?: File) {
    if (!file) return;
    setError('');
    setBusy(true);
    setStatus('Uploading video…');
    try {
      const body = new FormData();
      body.append('video', file);
      const created = await api<Session>('/api/sessions', { method: 'POST', body });
      setSessions(current => [created, ...current]);
      select(created);
      setStatus('Video uploaded. Draw the monitoring area on the recording, then mark cleanup start and end.');
    } catch (e) {
      setError(message(e));
      setStatus('');
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    if (!active || !review) return;
    setBusy(true);
    setError('');
    try {
      const updated = await api<Session>(`/api/sessions/${active.id}/review`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(review),
      });
      setActive(updated);
      setReview(structuredClone(updated.review));
      setSessions(items => items.map(item => (item.id === updated.id ? updated : item)));
      setDirty(false);
      setStatus('Review saved on this computer.');
    } catch (e) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  function point(event: PointerEvent<HTMLDivElement>) {
    const box = surface.current!.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(1, (event.clientX - box.left) / box.width)),
      y: Math.max(0, Math.min(1, (event.clientY - box.top) / box.height)),
    };
  }

  function move(event: PointerEvent<HTMLDivElement>) {
    if (!start.current) return;
    const end = point(event);
    const begin = start.current;
    setDraftRegion({
      x: Math.min(begin.x, end.x),
      y: Math.min(begin.y, end.y),
      width: Math.abs(end.x - begin.x),
      height: Math.abs(end.y - begin.y),
    });
  }

  function finish(event: PointerEvent<HTMLDivElement>) {
    if (!start.current || !review) return;
    move(event);
    const end = point(event);
    const begin = start.current;
    const next = {
      x: Math.min(begin.x, end.x),
      y: Math.min(begin.y, end.y),
      width: Math.abs(end.x - begin.x),
      height: Math.abs(end.y - begin.y),
    };
    if (next.width > 0.01 && next.height > 0.01) change({ ...review, region: next });
    start.current = null;
    setDraftRegion(null);
    setDrawing(false);
    event.currentTarget.releasePointerCapture(event.pointerId);
  }

  function addAnnotation() {
    if (!review || !note.trim() || !video.current) return;
    change({
      ...review,
      annotations: [
        ...review.annotations,
        { id: crypto.randomUUID(), seconds: video.current.currentTime, kind, note: note.trim(), source: 'manual' },
      ],
    });
    setNote('');
  }

  const region = draftRegion ?? review?.region;
  const ordered = [...(review?.annotations ?? [])].sort((a, b) => a.seconds - b.seconds);
  const windowInvalid = Boolean(
    review &&
      review.start_seconds !== null &&
      review.end_seconds !== null &&
      review.end_seconds <= review.start_seconds,
  );
  const path = [
    { id: 'sessions', label: 'Recordings', hint: 'Open a clip' },
    { id: 'evidence', label: 'Evidence', hint: 'Watch and mark what is visible' },
    { id: 'review', label: 'Review', hint: 'Cleanup window and notes' },
  ] as const;

  const checks = [
    { label: 'Recording open', done: Boolean(active) },
    { label: 'Monitoring area drawn', done: Boolean(review?.region) },
    { label: 'Cleanup start marked', done: review?.start_seconds !== null && review?.start_seconds !== undefined },
    { label: 'Cleanup end marked', done: review?.end_seconds !== null && review?.end_seconds !== undefined },
    { label: 'Saved on this computer', done: Boolean(active) && !dirty },
  ];

  return (
    <div className="desk">
      <aside className="pane pane-sessions">
        <div className="brand">
          <span className="mark" aria-hidden="true">
            G
          </span>
          <span>
            GLENWAKE
            <small>OPERATOR REVIEW DESK</small>
          </span>
        </div>
        <div className="pane-label">
          <span className="eyebrow">Left</span>
          <h2>Recordings</h2>
          <p>Choose a session, then work across the desk: evidence in the center, review on the right.</p>
        </div>
        <label className={`upload ${busy ? 'disabled' : ''}`}>
          <span>＋</span> Upload recording
          <input
            type="file"
            accept={VIDEO_ACCEPT}
            disabled={busy}
            onChange={e => {
              void upload(e.target.files?.[0]);
              e.target.value = '';
            }}
          />
        </label>
        <div className="session-list">
          {sessions.map(item => (
            <button
              key={item.id}
              className={`session ${active?.id === item.id ? 'selected' : ''}`}
              onClick={() => {
                if (dirty && !window.confirm('Discard unsaved review changes?')) return;
                select(item);
              }}
            >
              <span className="session-icon" aria-hidden="true">
                ▶
              </span>
              <span className="session-text">
                <strong title={item.filename}>{item.filename}</strong>
                <small>{sessionMeta(item)}</small>
              </span>
            </button>
          ))}
          {!sessions.length && (
            <div className="empty-list">
              No recordings yet.
              <br />
              Upload a stationary-camera clip to begin. Analysis has not run.
            </div>
          )}
        </div>
        <div className="sidebar-foot">
          LOCAL DESK <span className="online-dot" />
          <br />
          <small>Original recordings stay on this computer. Nothing here is model output.</small>
        </div>
      </aside>

      <div className="desk-surface">
        <header className="desk-rail">
          <nav className="path" aria-label="Review path">
            {path.map((step, index) => (
              <span key={step.id} className={`path-step ${!active && step.id === 'sessions' ? 'current' : ''} ${active && step.id === 'sessions' ? 'done' : ''} ${active && step.id !== 'sessions' ? 'current' : ''}`}>
                <span className="path-index">{index + 1}</span>
                <span className="path-copy">
                  <strong>{step.label}</strong>
                  <small>{step.hint}</small>
                </span>
                {index < path.length - 1 && <span className="path-arrow" aria-hidden="true" />}
              </span>
            ))}
          </nav>
          <div className="rail-meta">
            <span className="filename">{active ? active.filename : 'No recording open'}</span>
            <span className="manual-chip">Manual review only</span>
          </div>
        </header>

        {error && (
          <div role="alert" className="error">
            {error}
          </div>
        )}
        {status && (
          <div role="status" className="status">
            {status}
          </div>
        )}

        <div className="desk-body">
          <section className="pane pane-evidence" aria-label="Evidence">
            <div className="pane-kicker">
              <span className="eyebrow">Center · Evidence</span>
              <h1>Recording and visible events</h1>
              <p>Inspect the original video, draw one monitoring rectangle, then log what you can see. No automatic detections are shown.</p>
            </div>

            <article className="card player-card">
              <div className="card-head">
                <span>Original recording</span>
                <span>{review?.region ? 'Monitoring area on frame' : 'No monitoring area'}</span>
              </div>
              {!active || !review ? (
                <div className="empty-stage">
                  <p className="empty-title">No clip on the desk</p>
                  <p>Upload a recording from the left pane. Automatic analysis has not run and is unavailable.</p>
                  <label className="primary-upload">
                    Upload a recording
                    <input
                      type="file"
                      accept={VIDEO_ACCEPT}
                      onChange={e => {
                        void upload(e.target.files?.[0]);
                        e.target.value = '';
                      }}
                    />
                  </label>
                </div>
              ) : (
                <>
                  <div
                    ref={surface}
                    className={`video-surface ${drawing ? 'draw-mode' : ''}`}
                    onPointerDown={e => {
                      if (!drawing) return;
                      start.current = point(e);
                      e.currentTarget.setPointerCapture(e.pointerId);
                    }}
                    onPointerMove={move}
                    onPointerUp={finish}
                    onPointerCancel={e => {
                      start.current = null;
                      setDraftRegion(null);
                      setDrawing(false);
                      if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
                    }}
                  >
                    <video ref={video} key={active.id} controls playsInline src={active.video_url} />
                    {region && (
                      <div
                        className="region"
                        style={{
                          left: `${region.x * 100}%`,
                          top: `${region.y * 100}%`,
                          width: `${region.width * 100}%`,
                          height: `${region.height * 100}%`,
                        }}
                      >
                        <span>Monitoring area</span>
                      </div>
                    )}
                    {drawing && <div className="draw-hint">Drag across the video to mark the area</div>}
                  </div>
                  <div className="player-actions">
                    <button
                      className={drawing ? 'active-button' : ''}
                      onClick={() => {
                        video.current?.pause();
                        setDrawing(!drawing);
                      }}
                    >
                      {drawing ? 'Cancel drawing' : review.region ? 'Redraw monitoring area' : 'Draw monitoring area'}
                    </button>
                    <span>
                      {review.region
                        ? 'Rectangle is a review boundary only — not a detected mask.'
                        : 'Draw a rectangle on the frame. Litter masks are not available.'}
                    </span>
                  </div>
                </>
              )}
            </article>

            <article className="card timeline">
              <div className="card-head">
                <span>Timestamped events</span>
                <span>{ordered.length === 1 ? '1 observation' : `${ordered.length} observations`}</span>
              </div>
              <div className="timeline-title">
                <h2>What is visible?</h2>
                <p>Pause at a useful moment, record the observation, then use its time to jump back. These entries are manual.</p>
              </div>
              <div className="event-form">
                <select
                  aria-label="Event type"
                  value={kind}
                  disabled={!review}
                  onChange={e => setKind(e.target.value as Annotation['kind'])}
                >
                  {kinds.map(k => (
                    <option key={k.value} value={k.value}>
                      {k.label}
                    </option>
                  ))}
                </select>
                <input
                  aria-label="Observation"
                  placeholder={review ? 'Describe what is visible in the frame…' : 'Open a recording first'}
                  value={note}
                  disabled={!review}
                  onChange={e => setNote(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') addAnnotation();
                  }}
                />
                <button disabled={!review || !note.trim()} onClick={addAnnotation}>
                  Add at playhead
                </button>
              </div>
              <div className="events">
                {ordered.map(event => (
                  <div className="event" key={event.id}>
                    <button
                      className="event-time"
                      onClick={() => {
                        if (video.current) {
                          video.current.currentTime = event.seconds;
                          video.current.pause();
                        }
                      }}
                    >
                      {time(event.seconds)}
                    </button>
                    <div>
                      <strong>{kinds.find(k => k.value === event.kind)?.label}</strong>
                      <p>{event.note}</p>
                      <small>Manual observation</small>
                    </div>
                    <button
                      aria-label="Remove observation"
                      className="remove"
                      onClick={() => change({ ...review!, annotations: review!.annotations.filter(a => a.id !== event.id) })}
                    >
                      ×
                    </button>
                  </div>
                ))}
                {!ordered.length && (
                  <div className="empty-events">
                    No events yet. Automatic detection is unavailable — add a manual observation at the current playhead.
                  </div>
                )}
              </div>
            </article>
          </section>

          <section className="pane pane-review" aria-label="Review">
            <div className="pane-kicker">
              <span className="eyebrow">Right · Review</span>
              <h1>Cleanup window and notes</h1>
              <p>Mark when cleanup began and ended, then record limits the video cannot settle.</p>
            </div>

            <aside className="unavailable" role="status">
              <strong>Analysis has not run</strong>
              <p>Segmentation, coverage, and attribution are not available in this workspace. Do not treat the empty frame as a completed result.</p>
            </aside>

            <article className="card">
              <div className="card-head">
                <span>Cleanup window</span>
                <span>Start and end</span>
              </div>
              <div className="panel-body">
                <h2>Set the boundaries</h2>
                <p>
                  {review
                    ? 'Play or seek to each moment on the recording, then mark it here.'
                    : 'Open a recording to mark cleanup start and end. Markers stay empty until you set them.'}
                </p>
                <div className="marker">
                  <div>
                    <small>Start</small>
                    <strong>{time(review?.start_seconds ?? null)}</strong>
                  </div>
                  <button disabled={!review} onClick={() => change({ ...review!, start_seconds: video.current?.currentTime ?? 0 })}>
                    Mark current time
                  </button>
                </div>
                <div className="marker">
                  <div>
                    <small>End</small>
                    <strong>{time(review?.end_seconds ?? null)}</strong>
                  </div>
                  <button disabled={!review} onClick={() => change({ ...review!, end_seconds: video.current?.currentTime ?? 0 })}>
                    Mark current time
                  </button>
                </div>
                {windowInvalid && <p className="validation">End must be after start before saving.</p>}
              </div>
            </article>

            <article className="card notes-card">
              <div className="card-head">
                <span>Reviewer notes</span>
                <span>Human input</span>
              </div>
              <div className="panel-body">
                <h2>Conditions and uncertainty</h2>
                <p>Record blocked views, camera limits, or anything the still frame cannot prove.</p>
                <textarea
                  aria-label="Reviewer notes"
                  placeholder={
                    review
                      ? 'Example: A truck blocks the area between 01:20 and 01:45. The object origin remains unclear.'
                      : 'Open a recording to add notes.'
                  }
                  value={review?.notes ?? ''}
                  disabled={!review}
                  onChange={e => change({ ...review!, notes: e.target.value })}
                />
                <div className="note-caption">These notes are yours. GlenWake has not analyzed the video automatically.</div>
              </div>
            </article>

            <div className="save-row">
              <button className="save" disabled={busy || !dirty || !review || Boolean(windowInvalid)} onClick={() => void save()}>
                {busy ? 'Working…' : dirty ? 'Save review' : review ? 'Saved' : 'Nothing to save'}
              </button>
            </div>

            <div className="guide">
              <span>Evidence to review</span>
              <ol>
                {checks.map(item => (
                  <li key={item.label} className={item.done ? 'done' : ''}>
                    {item.label}
                  </li>
                ))}
              </ol>
              <p>Observations under the video are evidence. The right pane is the review of that evidence. Save, then reopen the session from the left to confirm it persisted.</p>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
