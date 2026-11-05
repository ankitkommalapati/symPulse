import { useEffect, useState } from 'react';
import type { Analysis, Bundle, Meta, Packet, Resource, SourceInventory, SourceRecord } from '../types';

export async function fetchJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
  if (!response.ok) {
    let message = `Request could not be completed (${response.status})`;
    try { const body = await response.json(); if (typeof body.detail === 'string') message = body.detail; } catch { /* Use the HTTP status. */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
export function withClock(path: string, clock: string) {
  return clock ? `${path}${path.includes('?') ? '&' : '?'}as_of=${encodeURIComponent(clock)}` : path;
}
export function useBundle(clock: string, revision: number): Resource<Bundle> {
  const [state, setState] = useState<Resource<Bundle>>({ status: 'loading' });
  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    Promise.all([
      fetchJson<Meta>('/api/meta', controller.signal),
      fetchJson<Analysis>(withClock('/api/intelligence/units', clock), controller.signal),
      fetchJson<{ items: SourceInventory[] }>(withClock('/api/sources', clock), controller.signal),
      fetchJson<{ items: (SourceRecord & { name: string })[] }>(withClock('/api/records/facilities', clock), controller.signal),
    ]).then(([meta, analysis, sources, facilities]) => {
      if (!controller.signal.aborted) setState({ status: 'ready', data: { meta, analysis, sources: sources.items,
        hospital: facilities.items[0]?.name || 'Hospital operations' } });
    }).catch(error => { if (!controller.signal.aborted) setState({ status: 'error', message: String(error.message || error) }); });
    return () => controller.abort();
  }, [clock, revision]);
  return state;
}
export function usePacket(id: string, clock: string, revision: number): Resource<Packet> {
  const [state, setState] = useState<Resource<Packet>>({ status: 'loading' });
  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    fetchJson<Packet>(withClock(`/api/investigations/${encodeURIComponent(id)}`, clock), controller.signal)
      .then(data => { if (!controller.signal.aborted) setState({ status: 'ready', data }); })
      .catch(error => { if (!controller.signal.aborted) setState({ status: 'error', message: String(error.message || error) }); });
    return () => controller.abort();
  }, [id, clock, revision]);
  return state;
}
