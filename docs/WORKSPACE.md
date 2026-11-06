# Operational workspace

The workspace makes the deterministic intelligence engine inspectable: overview → department investigation → calculation → captured source revision. All displayed measurements come from the selected operational snapshot. No language model is required for this stage.

## Run the application

Use Python 3.9+ and Node.js 22.12+ with npm. Install and build from the project root:

```text
python -m pip install -r requirements.lock
python -m pulse prepare
npm --prefix apps/web ci
npm --prefix apps/web run build
python -m pulse serve
```

Open `http://127.0.0.1:8000`. The existing FastAPI process serves both the built React workspace and API. Rebuild after frontend changes, then restart the service if it was started before the first frontend build. No additional database or storage service is required.

For frontend development, keep the API on its default port and run `npm --prefix apps/web run dev` in a separate terminal. Vite proxies API requests to the service. The built application uses same-origin requests and requires no proxy, credentials or external font service.

React and Vite keep the existing Python service as the application runtime. This replaces the proposed Next.js frontend for this prototype: server rendering is unnecessary for an internal operational workspace, and a static build avoids a second application server. Exact dependency versions and the npm lockfile make installation reproducible.

## Appearance

The sun/moon button in the header switches between light and dark mode. The selection is saved in browser storage and shared across tabs. With no saved selection, the workspace follows the system color preference, including changes while open. If storage is blocked, switching still works for the current mounted workspace. A small same-origin script applies the initial theme before the interface paints.

Brand backgrounds use `#6100DC` with purple-tinted supporting surfaces. The unspaced `symPulse` wordmark keeps its green `Pulse` text in both themes. Cards, charts, forms and evidence dialogs share theme tokens; amber and blue continue to distinguish operational statuses.

## Review flow

1. **Overview:** six department summaries, actual hour/visit measurements, one high-priority ICU investigation and one informational Step-down reporting review at the default clock. No invented health score or clinical risk probability.
2. **Investigation:** the next 72 hours align nurse coverage, physician authorization and vendor visits. Historical overtime and quality-report windows supply context. Select a metric or timeline commitment to inspect supporting records.
3. **Overtime chart:** switch day/night series and inspect dates by pointer or keyboard. A fixed baseline is separate from the changing monitoring period. Missing dates remain gaps. The baseline-average line is descriptive; the detector uses the weekday-adjusted EWMA calculation described in the evidence.
4. **Evidence library:** grouped source revisions, calculation formulas, searchable paginated records, availability timestamps and payload hashes. The evidence drawer uses records captured with the investigation rather than re-querying a newer version. Download evidence exports that complete JSON packet.
5. **Limits & uncertainty:** unconfirmed contributing context, reporting lag, quality denominators and explicit limits remain visible. Pending renewal is distinguished from uncovered authorization.
6. **Data sources:** browse 21 collections across six source families. Opening a record first persists its source evidence object through the existing API.
7. **Knowledge snapshot:** select the default time, four hours earlier or an explicit custom UTC instant. Display time uses the hospital timezone. The URL retains `as_of`; bookmarks and browser history preserve the selected snapshot. Refresh repeats the current snapshot.

The dataset is an archive, so live delivery freshness is explicitly unmeasured. Loading, request failure, unknown investigation, insufficient history and empty source/search states have distinct messages. Later evidence never enters an earlier replay. Refresh/replay clears old evidence state and cancels outstanding reads.

Native modal dialogs provide focus containment and Escape handling. Investigation tabs support arrow/Home/End navigation; the chart supports arrow navigation; buttons and links expose names and focus states. Layout rules cover narrow screens, with horizontal scrolling for dense timelines. A visual browser review is still required to confirm actual rendering and responsive appearance.

## Verification

```text
python -m unittest discover -s tests -v
npm --prefix apps/web test
npm --prefix apps/web run build
python scripts/smoke_workspace.py
```

`smoke_workspace.py` owns an isolated loopback listener, fetches the built entry assets, and runs the React integration tests against the real HTTP service and generated database. It terminates the listener even on failure. These integration tests run in jsdom, which does not assess pixels, native focus trapping or browser downloads. The ordinary frontend suite skips the two live tests when the verification listener is absent.

Stage 3 results: 65 Python tests, 10 component tests and 2 live HTTP-to-React tests passed; strict TypeScript and the production build passed. Live checks trace the ICU measurement to its saved absence revision, browse a source record, use investigation tabs, replay an earlier snapshot and display an unknown-investigation error. Automated browser preview was blocked by the browser URL policy, so browser appearance, mobile layout and native download behavior remain unverified.

## Stage boundary

This stage provides a read-only operational workspace with evidence persistence. Suggested review owners are text from the deterministic engine. Stage 4 adds the Compare interventions tab; see [staffing simulation](SIMULATION.md). Generated AI explanations and approval/task workflows remain separate stages.
