import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { Activity, Building2, ChevronDown, Clock3, Database, Files, LayoutDashboard, RefreshCw, ShieldCheck, Menu, X } from 'lucide-react';
import type { Bundle, Route } from './types';
import { dateTime, readRoute } from './lib/format';
import { useBundle } from './lib/api';
import { ErrorState, Loading } from './components/Common';
import Overview from './components/Overview';
import ThemeToggle from './components/ThemeToggle';
import Investigations from './components/Investigations';
import type { DrawerSelection } from './components/EvidenceDrawer';

const Verification = lazy(() => import('./components/Verification'));
const Investigation = lazy(() => import('./components/Investigation'));
const Sources = lazy(() => import('./components/Sources'));
const EvidenceDrawer = lazy(() => import('./components/EvidenceDrawer'));
const SnapshotDialog = lazy(() => import('./components/SnapshotDialog'));

function Workspace({ route, clock, revision, retry, changeClock }: { route: Route; clock: string; revision: number; retry: () => void; changeClock: (clock: string) => void }) {
  const resource = useBundle(clock, revision);
  const [drawer, setDrawer] = useState<DrawerSelection | null>(null);
  const [snapshotOpen, setSnapshotOpen] = useState(false);
  const keyboardNavigation = useRef(true);
  const [sidebarHovered, setSidebarHovered] = useState(false);
  const [sidebarFocused, setSidebarFocused] = useState(false);
  const [touchSidebarOpen, setTouchSidebarOpen] = useState(false);
  const [finePointer, setFinePointer] = useState(() => window.matchMedia?.('(hover: hover) and (pointer: fine)').matches ?? true);
  const collapsed = !(finePointer ? sidebarHovered || sidebarFocused : touchSidebarOpen);
  useEffect(() => {
    const query = window.matchMedia?.('(hover: hover) and (pointer: fine)');
    const sync = () => { setFinePointer(query?.matches ?? true); setSidebarHovered(false); setSidebarFocused(false); setTouchSidebarOpen(false); };
    const pointer = () => { keyboardNavigation.current = false; };
    const keyboard = (event: KeyboardEvent) => { if (event.key === 'Tab') keyboardNavigation.current = true; };
    query?.addEventListener('change', sync);
    document.addEventListener('pointerdown', pointer, true);
    document.addEventListener('keydown', keyboard, true);
    return () => { query?.removeEventListener('change', sync); document.removeEventListener('pointerdown', pointer, true); document.removeEventListener('keydown', keyboard, true); };
  }, []);
  const openDrawer = useCallback((selection: DrawerSelection) => setDrawer(selection), []);
  const bundle: Bundle | undefined = resource.status === 'ready' ? resource.data : undefined;
  const activePage = route.page === 'investigation' ? 'investigations' : route.page;
  const highCount = bundle?.analysis.units.filter(unit => unit.priority === 'high').length;
  return <div className={`app-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
    <a className="skip-link" href="#main-content" onClick={event => { event.preventDefault(); document.getElementById('main-content')?.focus(); }}>Skip to workspace</a>
    <aside className="sidebar" aria-label="Workspace sidebar" data-expanded={!collapsed}
      onPointerEnter={event => { if (finePointer && event.pointerType !== 'touch') setSidebarHovered(true); }}
      onPointerLeave={() => setSidebarHovered(false)}
      onPointerDownCapture={() => setSidebarFocused(false)}
      onFocusCapture={() => { if (finePointer) setSidebarFocused(keyboardNavigation.current); }}
      onBlurCapture={event => { if (!(event.relatedTarget instanceof Node) || !event.currentTarget.contains(event.relatedTarget)) setSidebarFocused(false); }}>
<div className="sidebar-header"><a className="brand" href="#overview" aria-label="symPulse home"><span className="brand-mark"><Activity size={24} /></span><strong>sym<span>Pulse</span></strong></a>{!finePointer ? <button type="button" className="sidebar-toggle" aria-label={collapsed ? 'Open navigation' : 'Close navigation'} aria-expanded={!collapsed} aria-controls="workspace-navigation" onClick={() => setTouchSidebarOpen(value => !value)}>{collapsed ? <Menu size={17} /> : <X size={17} />}</button> : null}</div>
      <div className="nav-label">WORKSPACE</div><nav id="workspace-navigation" aria-label="Main navigation">{[
        { id: 'overview', label: 'Overview', icon: LayoutDashboard }, { id: 'investigations', label: 'Investigations', icon: Files }, { id: 'sources', label: 'Data sources', icon: Database }, { id: 'verification', label: 'Demo evidence', icon: ShieldCheck },
      ].map(({ id, label, icon: Icon }) => <a key={id} href={`#${id}`} aria-label={label} title={collapsed ? label : undefined} className={activePage === id ? 'active' : ''} aria-current={activePage === id ? 'page' : undefined}><Icon size={18} /><span>{label}</span>{id === 'investigations' && highCount ? <b>{highCount}</b> : null}</a>)}</nav>
      <div className="sidebar-bottom"><div className="sidebar-note"><ShieldCheck size={20} /><strong>Clarity you can trace.</strong><p>Every investigation leads back to its supporting records.</p></div><div className="demo-label"><span />SYNTHETIC DEMONSTRATION</div></div>
    </aside>
    <div className="app-main"><header className="topbar"><div className="hospital"><Building2 size={18} /><span>{bundle?.hospital || 'Hospital operations'}</span></div><div className="header-actions"><ThemeToggle /><button className="snapshot-control" disabled={!bundle} onClick={() => setSnapshotOpen(true)}><Clock3 size={16} /><span><small>KNOWLEDGE SNAPSHOT</small><strong>{bundle ? dateTime(bundle.analysis.as_of, bundle.meta.hospital_timezone, { timeZoneName: 'short' }) : 'Loading snapshot…'}</strong></span><ChevronDown size={13} /></button><button className="icon-button refresh" aria-label="Refresh current snapshot" onClick={retry}><RefreshCw size={17} /></button><span className="avatar" aria-label="Operations reviewer">OP</span></div></header>
      <main id="main-content" className="workspace" tabIndex={-1}>{resource.status === 'loading' ? <Loading /> : resource.status === 'error' ? <ErrorState message={resource.message} retry={retry} /> : <Suspense fallback={<Loading />}>
        {route.page === 'overview' ? <Overview bundle={resource.data} /> : route.page === 'investigations' ? <Investigations bundle={resource.data} /> : route.page === 'verification' ? <Verification clock={resource.data.analysis.as_of} /> : route.page === 'sources' ? <Sources bundle={resource.data} openDrawer={openDrawer} /> : <Investigation key={`${route.id}:${resource.data.analysis.as_of}`} id={route.id} bundle={resource.data} revision={revision} retry={retry} openDrawer={openDrawer} />}
      </Suspense>}</main>
      <footer className="workspace-footer"><span>symPulse · Concept prototype</span><span>Evidence-backed operational decision support</span></footer>
    </div>
    <Suspense fallback={null}>{drawer && bundle ? <EvidenceDrawer key={`${drawer.title}:${drawer.initialRecord || ''}`} selection={drawer} zone={bundle.meta.hospital_timezone} close={() => setDrawer(null)} /> : null}{snapshotOpen && bundle ? <SnapshotDialog current={bundle.analysis.as_of} defaultClock={bundle.meta.as_of} zone={bundle.meta.hospital_timezone} close={() => setSnapshotOpen(false)} change={changeClock} /> : null}</Suspense>
  </div>;
}

export default function App() {
  const [route, setRoute] = useState<Route>(readRoute);
  const [clock, setClock] = useState(() => new URLSearchParams(location.search).get('as_of') || '');
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    const sync = () => { setRoute(readRoute()); setClock(new URLSearchParams(location.search).get('as_of') || ''); };
    window.addEventListener('hashchange', sync); window.addEventListener('popstate', sync);
    return () => { window.removeEventListener('hashchange', sync); window.removeEventListener('popstate', sync); };
  }, []);
  const retry = useCallback(() => setRevision(value => value + 1), []);
  const changeClock = useCallback((value: string) => {
    const url = new URL(location.href); url.searchParams.set('as_of', value); history.replaceState(null, '', url);
    setClock(value);
  }, []);
  return <Workspace key={`${clock}:${revision}`} route={route} clock={clock} revision={revision} retry={retry} changeClock={changeClock} />;
}
