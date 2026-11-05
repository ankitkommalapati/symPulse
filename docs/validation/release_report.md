# Recorded release verification

Application: 0.7.0. Generated: 2026-11-05T10:43:16.896883+00:00.

Status: **review ready with verification gaps**.

## Automated checks

| Check | Status | Tests | Elapsed seconds |
|---|---|---:|---:|
| python_regressions | passed | 128 | 70.797 |
| frontend_components | passed | 26 | 1.623 |
| production_build | passed | — | 0.525 |
| live_http_react | passed | 2 | 16.014 |

## Synthetic fixtures

26 fully matched, 3 partial, 1 mismatched, 0 adapter errors. No pooled accuracy claim.

| Family | Split | TP / FP / FN / TN | Precision | Recall |
|---|---|---|---:|---:|
| access | tune | 1 / 0 / 0 / 1 | 100.0% | 100.0% |
| access | holdout | 1 / 1 / 0 / 2 | 50.0% | 100.0% |
| drift | tune | 1 / 0 / 0 / 1 | 100.0% | 100.0% |
| drift | holdout | 1 / 0 / 0 / 3 | 100.0% | 100.0% |
| provider | tune | 1 / 0 / 0 / 1 | 100.0% | 100.0% |
| provider | holdout | 2 / 0 / 0 / 2 | 100.0% | 100.0% |
| quality | tune | 1 / 0 / 0 / 1 | 100.0% | 100.0% |
| quality | holdout | 0 / 0 / 0 / 4 | — | — |
| simulation | tune | 1 / 0 / 0 / 1 | 100.0% | 100.0% |
| simulation | holdout | 0 / 0 / 0 / 4 | — | — |

## API timings

Three in-process HTTP samples; excludes browser layout, network transit and human review.

| Operation | Median seconds | Min–max seconds |
|---|---:|---:|
| analysis_cold | 0.901 | 0.896–0.907 |
| analysis_cached | 0.001 | 0.001–0.001 |
| simulation_context | 4.886 | 4.882–4.904 |
| simulate_hybrid | 2.322 | 2.287–2.328 |
| brief_fallback | 0.013 | 0.013–0.013 |
| brief_cached | 0.011 | 0.011–0.011 |
| approve | 0.012 | 0.012–0.019 |
| close | 0.013 | 0.013–0.013 |

## Rehearsal and outstanding gates

Three API rehearsals: 3/3 passed. Identical core arithmetic: True.

- automated_regressions: passed
- repeatable_demo_api: passed
- no_unexpected_fixture_discrepancies: passed
- all_fixture_cases_fully_matched: outstanding
- visual_browser_verified: outstanding
- live_model_verified: outstanding

## Claim limits

- Synthetic component challenges; not production accuracy or clinical validation
- Tune/holdout labels were generated before the engine but were visible during development; not a blind held-out study
- Live source delivery freshness is unmeasured; unsupported fixture fields remain partial
- No real-model inference or visual browser verification was completed
- The simulation holdout has no feasible positive case; its precision/recall are undefined
- API timing samples use an in-process HTTP test client; exclude browser layout, network transit and human investigation time
- Atomic findings grouped by investigation are not a measured alert-noise or precision improvement

The Access late-arrival fixture remains mismatched pending label/data-contract review. See the JSON report for every expected/observed value and unsupported field.
