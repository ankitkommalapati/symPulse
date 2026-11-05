import { AlertCircle, ArrowRight, LoaderCircle } from 'lucide-react';
import type { ReactNode } from 'react';
import type { Priority } from '../types';

const labels: Record<Priority, string> = { high: 'High priority', medium: 'Needs attention',
  informational: 'For review', review_required: 'Data review', none: 'No current finding' };
export function Badge({ priority }: { priority: Priority }) {
  return <span className={`badge badge-${priority}`}><span className="status-dot" />{labels[priority]}</span>;
}
export function Loading({ label = 'Connecting the evidence…' }: { label?: string }) {
  return <div className="loading-state" role="status"><LoaderCircle className="spin" size={25} /><h2>{label}</h2><p>Reviewing the records known at this snapshot.</p></div>;
}
export function ErrorState({ message, retry }: { message: string; retry: () => void }) {
  return <div className="error-state" role="alert"><AlertCircle size={30} /><h2>This view couldn’t be loaded</h2><p>{message}</p><button className="button primary" onClick={retry}>Try again <ArrowRight size={16} /></button></div>;
}
export function EvidenceButton({ onClick, children = 'View evidence' }: { onClick: () => void; children?: ReactNode }) {
  return <button className="text-button" onClick={onClick}>{children}<ArrowRight size={14} /></button>;
}
