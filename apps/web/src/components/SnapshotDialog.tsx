import { useEffect, useRef, useState } from 'react';
import { Clock3, X } from 'lucide-react';
import { dateTime } from '../lib/format';

export default function SnapshotDialog({ current, defaultClock, zone, close, change }: { current: string; defaultClock: string; zone: string; close: () => void; change: (clock: string) => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [value, setValue] = useState(new Date(current).toISOString().slice(0, 16));
  const [error, setError] = useState('');
  useEffect(() => { const node = dialog.current; node?.showModal(); return () => { if (node?.open) node.close(); }; }, []);
  function apply(clock: string) { change(clock); close(); }
  return <dialog ref={dialog} className="snapshot-dialog" aria-labelledby="snapshot-title" onCancel={event => { event.preventDefault(); close(); }}>
    <div className="drawer-header"><div><span className="eyebrow">WHAT WAS KNOWN THEN?</span><h2 id="snapshot-title">Review a snapshot</h2></div><button className="icon-button" aria-label="Close snapshot selector" onClick={close}><X size={20} /></button></div>
    <div className="snapshot-body"><p>Pulse uses only records available by the selected time. Future schedules can be known already; later reports stay out.</p>
      <button className="snapshot-option" onClick={() => apply(defaultClock)}><Clock3 size={18} /><span><strong>Demonstration snapshot</strong><small>{dateTime(defaultClock, zone)} · {zone}</small></span></button>
      <button className="snapshot-option" onClick={() => apply(new Date(new Date(defaultClock).getTime() - 4 * 3600000).toISOString())}><Clock3 size={18} /><span><strong>Four hours earlier</strong><small>Compare the evidence available at an earlier point.</small></span></button>
      <form onSubmit={event => { event.preventDefault(); const parsed = new Date(`${value}:00Z`); if (!value || !Number.isFinite(parsed.getTime())) { setError('Choose a valid date and time.'); return; } apply(parsed.toISOString()); }}><label htmlFor="custom-clock">Custom knowledge time (UTC)</label><input id="custom-clock" type="datetime-local" value={value} onChange={event => { setValue(event.target.value); setError(''); }} required /><small>The workspace displays this time in {zone}.</small>{error ? <p role="alert">{error}</p> : null}<button className="button primary" type="submit">Review this snapshot</button></form>
    </div>
  </dialog>;
}
