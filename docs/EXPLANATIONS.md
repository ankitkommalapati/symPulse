# Evidence briefs and bounded questions

The explanation layer turns the selected investigation into a readable, traceable brief. It does not calculate staffing, discover causes or execute actions. The investigation remains the authority for measurements; the simulator remains the authority for proposed coverage and cost.

## Product behavior

Open **Evidence brief** in an investigation. Choose one of five focused questions: overview, staffing evidence, why signals are grouped, limits, or remaining work. Statements link to their captured investigation evidence groups. A successfully calculated staffing scenario also shows a brief tied to that saved simulation, including its modeled cost, residual gap and unverified capacity.

Two visible modes are implemented:

- **AI-organized evidence brief:** a configured model selects an approved summary and orders certified statement IDs. The application validates the selection and renders its own statement text.
- **Rule-based evidence brief · fallback:** no model is configured, a provider fails, or its selection fails validation. The application uses a deterministic order and clearly labels the result.

This deliberately bounds the generative task. The model organizes verified statements rather than writing unrestricted prose. It cannot introduce measurements, new causal claims, invented evidence references or actions. Unconfirmed hypotheses remain labeled; mandatory unknowns cannot be omitted. There is no general-purpose chatbot or unrestricted database tool.

## Configuration

The default runs without any model credentials and uses the labeled fallback. Optional server settings are read from `.env` and process environment, with process values taking precedence:

| Setting | Meaning |
|---|---|
| `PULSE_LLM_ENDPOINT` | Full HTTPS Chat Completions-compatible endpoint; HTTP is allowed only on loopback |
| `PULSE_LLM_MODEL` | Model/deployment identifier supported by that endpoint; required together with endpoint |
| `PULSE_LLM_API_KEY` | Optional bearer credential for the endpoint; server only, never returned or logged |
| `PULSE_LLM_TIMEOUT_SECONDS` | Per-attempt total timeout, default 10, greater than zero and at most 30 |

Use a provider/model that supports JSON object response mode and `max_completion_tokens`. The adapter sends `model`, `messages`, `response_format: {type: json_object}` and a bounded output limit. It expects a stopped completion containing JSON text and preserves the returned model identifier. The request/response shape follows the [Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create); JSON format does not itself establish factual correctness, so application validation is required. There is no default vendor endpoint, model, account or external request.

The implemented adapter is for Chat Completions-compatible HTTP services. Native AWS Bedrock Converse, SigV4 authentication and vendor-specific APIs are not implemented by this adapter. No additional package or cloud resource is required for the existing provider interface or fallback.

## Certified catalog and validation

The backend constructs a bounded catalog from engine observations, measurements, existing review IDs, evidence groups, labeled hypotheses and unknowns. It includes the complete mandatory statement membership for each question. The model sees this catalog, not raw operational narrative fields or the full source archive.

The response contains exactly `summary_id`, `observation_ids`, `hypothesis_ids`, `unknown_ids`, `recommended_action_ids` and `remaining_risk_ids`. Strict schema validation rejects extra keys, free prose, wrong types, unsupported IDs, duplicates and omitted mandatory caveats. The server resolves IDs to its certified text and evidence groups. Every displayed number is produced by server logic from the captured investigation or simulation, not extracted from model prose.

This protects against unsupported claims through an allowlist contract; it is not a general natural-language entailment verifier. Expanding the catalog requires explicit application changes. Source data remains untrusted, and the model has no tools or write permissions.

A simulation explanation requires saved simulation evidence with the same investigation and snapshot identity. A different investigation, stale snapshot or unrelated artifact is rejected. Bounded question IDs are enforced by the API; arbitrary question text is not accepted.

## Failure handling and evidence

There are at most two provider attempts. Only timeouts, network failures, rate limits and server failures retry. Authentication rejection, redirects, refusal, truncated generation, malformed JSON and oversized responses fall back without exposing provider response bodies. Response content is capped at 64 KiB. An outer bound also limits the provider operation. Investigation retrieval and evidence persistence are outside that model time budget.

Successful model selections and fallbacks preserve the investigation/simulation identity, catalog hash, prompt version, requested/returned model, generation timestamp, selection, rendered statements and validation outcome as an immutable explanation artifact. Invalid raw model output is never displayed or persisted. `GET /api/artifacts/{digest}` retrieves the saved brief after restart.

A bounded 32-entry in-process cache keys by snapshot, question, simulation, catalog, prompt version, model and endpoint. Matching requests share a per-key lock. Successful model selections and unconfigured fallbacks remain cached until eviction; transient/invalid-output fallbacks expire after 15 seconds so a recovered provider can be tried again. Saved artifacts persist independently of the cache.

`POST /api/investigations/{id}/explain?as_of=...` accepts `snapshot_id`, a bounded `question`, and optional `simulation_id`. It returns the rendered brief and `explanation_id`/`artifact_url`. Stale or mismatched identities return 409, unknown investigation/artifact 404, unsupported questions or request shapes 422, and unavailable evidence storage 503.

## Verification and limits

Run the existing Python suite, frontend tests, production build and live workspace smoke script. Tests exercise valid mocked model selection, invalid claims/actions, omitted caveats, extra prose, duplicate IDs, refusals, truncation, malformed/oversized responses, retry limits, cancellation/timeouts, transient recovery, safe configuration, question scoping, snapshot mismatch, simulation grounding, persistent evidence, visible fallback and evidence links.

The live API-to-React flow opens the fallback brief, asks a limits question, calculates a staffing scenario and renders its explanation. Provider transport tests use controlled HTTP fixtures. No live model endpoint or credentials were supplied for this stage, so paid/provider inference, model-specific JSON-mode compatibility and explanation quality with a real model remain unverified. Browser appearance and native interactions also remain unverified following the existing browser URL policy block.

Approval, assignments, task ownership and resolution workflows are not part of this layer.

Stage 5 verification results: 100 Python tests, 19 component tests and 2 live HTTP-to-React tests passed, along with strict TypeScript and the production build. This count includes regression coverage from prior stages. Model-selection behavior is verified with deterministic provider fixtures; it is not a real-model quality evaluation.
