import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Info } from 'lucide-react';

/** Non-interactive help, available to pointer, touch and keyboard users. */
export default function InfoTip({ label, children }: { label: string; children: string }) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const tip = useRef<HTMLDivElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const cancelClose = () => window.clearTimeout(timer.current);
  const dismiss = () => { cancelClose(); setOpen(false); setPinned(false); setPosition(null); };
  const delayClose = () => {
    cancelClose();
    if (!pinned) timer.current = window.setTimeout(() => { setOpen(false); setPosition(null); }, 160);
  };
  useEffect(() => () => window.clearTimeout(timer.current), []);
  useLayoutEffect(() => {
    if (!open || !trigger.current || !tip.current) return;
    const anchor = trigger.current.getBoundingClientRect();
    const box = tip.current.getBoundingClientRect();
    const left = Math.max(12, Math.min(anchor.left, window.innerWidth - box.width - 12));
    const below = anchor.bottom + 10;
    const top = below + box.height <= window.innerHeight - 12 ? below : Math.max(12, anchor.top - box.height - 10);
    setPosition({ left, top });
  }, [open]);
  useEffect(() => {
    if (!open) return;
    const close = () => { window.clearTimeout(timer.current); setOpen(false); setPinned(false); setPosition(null); };
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (!trigger.current?.contains(target) && !tip.current?.contains(target)) close();
    };
    const scroll = (event: Event) => { if (!(event.target instanceof Node) || !tip.current?.contains(event.target)) close(); };
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') close(); };
    document.addEventListener('pointerdown', outside);
    document.addEventListener('keydown', key);
    window.addEventListener('resize', close);
    window.addEventListener('scroll', scroll, true);
    return () => {
      document.removeEventListener('pointerdown', outside); document.removeEventListener('keydown', key);
      window.removeEventListener('resize', close); window.removeEventListener('scroll', scroll, true);
    };
  }, [open]);
  return <>
    <button ref={trigger} type="button" className="info-button" aria-label={`About ${label}`} aria-expanded={open} aria-describedby={open ? id : undefined}
      onPointerEnter={event => { if (event.pointerType !== 'touch') { cancelClose(); setOpen(true); } }} onPointerLeave={delayClose}
      onFocus={() => { cancelClose(); setOpen(true); }} onBlur={dismiss}
      onClick={() => { cancelClose(); if (pinned) dismiss(); else { setPinned(true); setOpen(true); } }}><Info size={14} /></button>
    {open ? createPortal(<div ref={tip} id={id} role="tooltip" className="info-tooltip" style={{ left: position?.left ?? 12, top: position?.top ?? 12, visibility: position ? 'visible' : 'hidden' }} onPointerEnter={cancelClose} onPointerLeave={delayClose}>
      <strong>{label}</strong><p>{children}</p>
    </div>, document.body) : null}
  </>;
}
