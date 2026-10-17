// Builds OpsIntel_Diagram_Guide.docx - a page-by-page explanation of opsintel_architecture.drawio.
// Usage: npm install docx@9.5.1 && node docs/diagrams/build_guide.js docs/diagrams/OpsIntel_Diagram_Guide.docx
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  HeadingLevel, AlignmentType, LevelFormat, PageBreak, TableOfContents, Footer, PageNumber, Header,
} = require("docx");

const OUT = process.argv[2];
const CONTENT_W = 9026; // A4 width 11906 - 2 x 1440 margins

// ---------------------------------------------------------------- helpers
function runs(text, base = {}) {
  // **bold** and `code` inline markup
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...base }));
    else out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: (base.size || 21) - 2, color: "8B2E2E", ...base }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const P = (t, o = {}) => new Paragraph({ children: runs(t), spacing: { after: 120, line: 276 }, ...o });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)], pageBreakBefore: true });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)] });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)] });
const B = (t, level = 0) => new Paragraph({ numbering: { reference: "bullets", level }, children: runs(t), spacing: { after: 60, line: 264 } });
const N = (t) => new Paragraph({ numbering: { reference: "numbers", level: 0 }, children: runs(t), spacing: { after: 60, line: 264 } });

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };

function cell(text, width, opts = {}) {
  const paras = String(text).split("\n").map((line) => new Paragraph({ children: runs(line, { size: opts.size || 19, bold: opts.bold }), spacing: { after: 40, line: 252 } }));
  return new TableCell({
    children: paras, width: { size: width, type: WidthType.DXA }, borders,
    shading: opts.fill ? { fill: opts.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 70, bottom: 70, left: 110, right: 110 },
  });
}
function table(headers, rows, ratios, headFill = "1F3864") {
  const total = ratios.reduce((a, b) => a + b, 0);
  const widths = ratios.map((r) => Math.floor((r / total) * CONTENT_W));
  widths[widths.length - 1] += CONTENT_W - widths.reduce((a, b) => a + b, 0);
  const head = new TableRow({ tableHeader: true, children: headers.map((h, i) => new TableCell({
    children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, color: "FFFFFF", size: 19 })] })],
    width: { size: widths[i], type: WidthType.DXA }, borders, shading: { fill: headFill, type: ShadingType.CLEAR, color: "auto" },
    margins: { top: 70, bottom: 70, left: 110, right: 110 } })) });
  const body = rows.map((r, ri) => new TableRow({ children: r.map((c, i) => cell(c, widths[i], { fill: ri % 2 ? "F4F6FA" : undefined, bold: i === 0 })) }));
  return [new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: widths, rows: [head, ...body] }), new Paragraph({ spacing: { after: 160 } })];
}
function callout(title, text, fill = "EAF1FB", edge = "2F5597") {
  const side = { style: BorderStyle.SINGLE, size: 18, color: edge };
  const none = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  return [new Table({ width: { size: CONTENT_W, type: WidthType.DXA }, columnWidths: [CONTENT_W], rows: [new TableRow({ children: [new TableCell({
    width: { size: CONTENT_W, type: WidthType.DXA }, borders: { left: side, top: none, bottom: none, right: none },
    shading: { fill, type: ShadingType.CLEAR, color: "auto" }, margins: { top: 100, bottom: 100, left: 180, right: 180 },
    children: [new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 20, color: edge })], spacing: { after: 60 } }),
      ...text.split("\n").map((t) => new Paragraph({ children: runs(t, { size: 20 }), spacing: { after: 50, line: 264 } }))] })] })] }),
    new Paragraph({ spacing: { after: 160 } })];
}
// Decision table: condition, outcomes, why
const decision = (rows) => table(["Decision point", "Outcomes", "Why it is designed this way"], rows, [2.2, 3, 4.3], "7B2C2C");
const blocks = (rows) => table(["Block", "What it is / what it does", "Design rationale & where in the code"], rows, [2, 4, 3.6]);

// ---------------------------------------------------------------- content
const C = [];
const add = (...xs) => xs.forEach((x) => (Array.isArray(x) ? C.push(...x) : C.push(x)));

// Title page
add(
  new Paragraph({ spacing: { before: 2400 }, children: [new TextRun({ text: "OpsIntel AI", bold: true, size: 64, color: "1F3864" })] }),
  new Paragraph({ children: [new TextRun({ text: "Architecture & Design Flow Guide", size: 40, color: "2F5597" })], spacing: { after: 240 } }),
  new Paragraph({ children: [new TextRun({ text: "A page-by-page explanation of every block, flow and decision in opsintel_architecture.drawio", size: 24, color: "595959" })], spacing: { after: 600 } }),
  P("**Project:** OpsIntel AI - a governed, LLM-assisted operational intelligence platform for IT service businesses (proof of concept on synthetic data)."),
  P("**Companion files:** `docs/diagrams/opsintel_architecture.drawio` (the diagrams), `docs/diagrams/build_diagrams.py` (generates them), `docs/architecture.md`, `docs/evaluation_report.md`."),
  P("**Data notice:** figures on pages 1-9 come from the synthetic data set (fictional company, seed 42, snapshot 30 September 2026). Page 10 figures come from a ServiceNow developer instance (ServiceNow demo records plus history seeded by this project). Nothing describes a real organisation."),
  new Paragraph({ children: [new PageBreak()] }),
  new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("Contents")] }),
  new TableOfContents("Contents", { hyperlink: true, headingStyleRange: "1-2" }),
  P("(Word asks to update fields when the file opens - choose Yes to fill in this list. If it stays empty, right-click it and choose Update Field.)"),
);

// How to read
add(H1("How to read the diagrams"));
add(P("The file contains ten pages, shown as tabs along the bottom of draw.io. Each page answers one question about the design. The pages use the same visual language throughout, so once you know the conventions below you can read any page."));
add(H2("Colour = architectural layer"));
add(table(["Colour", "Layer", "Meaning"], [
  ["Blue", "Enterprise sources", "Systems the platform reads from. It never writes back to them."],
  ["Green", "Integration & data quality", "Code that extracts, cleans, matches, validates and records lineage."],
  ["Yellow", "Data foundation", "Stored, typed, documented data: tables, views, catalogue, document index."],
  ["Purple", "Analytics engine", "Deterministic calculations: KPIs, anomaly detection, risk scoring."],
  ["Red / pink", "AI engine", "The assistant: Claude engine, rules engine, tools, retrieval, guarded SQL, grounding check."],
  ["Orange", "Interface", "What people and other systems touch: dashboard, REST API, CLI."],
  ["Grey", "Governance", "Cross-cutting controls: access, privacy, injection screening, approvals, audit."],
  ["White", "External / user", "People, outside services (Anthropic API, webhooks) and neutral notes."],
], [1.3, 2.2, 5.5]));
add(H2("Shapes and lines"));
add(table(["Shape / line", "Meaning"], [
  ["Rounded rectangle", "A component or process step. Bold first line = name; smaller text = what it does."],
  ["Cylinder", "A data store (database, table, volume, index)."],
  ["Diamond", "A decision. Each outgoing arrow is labelled with the outcome (yes / no / value)."],
  ["Stick figure", "A person or an external system acting as a client."],
  ["Dashed rounded band", "A grouping (a layer, a deployment boundary). It has no behaviour of its own."],
  ["Solid arrow", "Main data or control flow, in the direction of the arrow."],
  ["Dashed arrow", "A return message, an optional path, or a governance relationship (control applies to)."],
  ["Pale-yellow note (sequence page)", "Work done inside one participant, not a message between participants."],
], [2.4, 6.6]));
add(callout("The one idea that runs through all ten pages",
  "The language model sits on top of a deterministic analytics layer that it cannot bypass. It never touches the database directly; it asks for tools, and every tool call is validated, permission-checked, executed by tested code, screened, and recorded as numbered evidence. Answers are then checked figure-by-figure against that evidence. Every page below is a different view of that idea."));

// ================================================================ PAGE 1
add(H1("Page 1 - Layered architecture"));
add(P("**Question this page answers:** what are the parts of the system, how are they layered, and where does governance apply?"));
add(P("Read it top to bottom: data enters at layer 1 and becomes decisions at layer 5. The grey column on the right applies to every layer. The people at the bottom are the five user roles."));
add(H2("Layer 1 - Enterprise sources (blue)"));
add(blocks([
  ["CMDB (relational DB or live ServiceNow)", "Configuration management database holding business units, services (with alternative names), customers, assets/configuration items and SLA definitions. In synthetic mode it is a separate SQLite file (`data/raw/cmdb.sqlite`) with ServiceNow-like table names (`cmdb_service`, `cmdb_ci`, `core_company`, `sla_definition`). In live mode the same tables are read from a ServiceNow instance (page 10).", "Reference data is the backbone for matching everything else, so it is read first. Read-only connection (`mode=ro`) proves the platform cannot alter a source. Code: `etl/connectors.py::read_sql_table`."],
  ["ITSM (CSV or live ServiceNow)", "Incident and service-request records. In synthetic mode they arrive as exports, as a ServiceNow/Halo report would produce; in live mode they are read from the ServiceNow Table API with OAuth (page 10). 7,680 incident rows and 4,244 request rows arrive, including deliberate defects: duplicates, stale versions, two date formats, misspelled service names, missing priorities, test tickets, impossible timestamps and orphan customers.", "CSV export is the lowest-common-denominator integration every ITSM supports, so it is the realistic first step in a pilot. Defects are injected so data-quality handling can be measured, not assumed."],
  ["Finance ledger (CSV)", "Monthly cost lines per service and cost type (Staff, Licences, Third-party, Hardware, Energy) with a narrative description. Amounts arrive as strings like `£12,345.67`, months as either `2026-09` or `Sep-2026`, plus re-export duplicates.", "Cost explanations need the ledger narrative (e.g. 'Hypervisor licence true-up'), not just numbers - that is what lets the assistant say *why* cost moved."],
  ["Monitoring platform (REST API)", "A paginated JSON API of monitoring events (`/v1/alerts?page=`). It mimics at-least-once delivery (150 duplicate events) and inconsistent severity case, and only knows asset ids, not services. A mock is bundled (`sources/mock_monitoring.py`); a real URL can be set with `OPSINTEL_MONITORING_URL`.", "Shows a genuine API integration with pagination, not just file drops. In-process mock keeps the demo offline while exercising the same HTTP contract."],
  ["Knowledge base", "Markdown runbooks, policies and a problem record, each with front-matter (id, owner, review date, classification public/internal/restricted). One vendor bulletin deliberately contains a prompt-injection payload.", "Front-matter classification enables document-level access control. The planted injection is how the security controls are tested end to end."],
]));
add(H2("Layer 2 - Integration & data quality (green)"));
add(blocks([
  ["Connectors", "Four connector types: CSV (read everything as text), relational (read-only SQL), REST (follows `next_page` until done), and ServiceNow (Table API, OAuth 2.0 client credentials, GET-only, lands into the same raw format). Each returns the data plus provenance: source URI and SHA-256 hash.", "Reading as text makes bad values visible instead of silently coerced. The hash proves exactly which file version produced a table. Code: `etl/connectors.py`."],
  ["Profiling", "The same quality metrics are computed on the raw data (before) and the loaded data (after): rows, missing required cells, exact duplicate rows, duplicate keys, schema violations, unmatched references.", "Measuring before and after turns 'we cleaned the data' into evidence. Results go to `dq_results` and the Data quality page. Code: `etl/quality.py::profile`."],
  ["Clean & conform", "Trim whitespace; parse ISO and UK `dd/mm/yyyy` dates; drop exact duplicates; keep the latest version of each incident by `sys_updated_on`; parse £ amounts; normalise month format and severity case.", "Each step is recorded by name (and count) in lineage, so an auditor can replay the reasoning. Code: `etl/pipeline.py`."],
  ["Entity matching", "Turns free-text service names into service ids in four tiers: normalised exact match → CMDB alias → fuzzy match (similarity ≥ 0.88) → unmatched (quarantined). On the incident export: 7,332 exact/normalised, 192 fuzzy, 0 unmatched.", "Free-text names are the most common integration failure between systems. Tiers make the matching explainable; the 0.88 cut-off favours precision (a wrong match is worse than a quarantined row). Code: `etl/quality.py::EntityMatcher`."],
  ["Validation & quarantine", "Rows that cannot be trusted go to `etl_rejects` with a reason and the original payload: test tickets, resolved-before-opened timestamps, orphan customers, unmatched services, unknown assets, duplicate ledger lines.", "Nothing is silently dropped. A data owner can inspect and fix rejects at source."],
  ["Lineage", "For every target table: run id, source name/type/URI, SHA-256, rows in/out/rejected, and the ordered list of transforms with counts.", "Answers 'where did this number come from?' all the way back to the source file. Code: `lineage` table."],
]));
add(H2("Layer 3 - Unified data foundation (yellow)"));
add(blocks([
  ["Operational store", "One typed schema with primary keys, foreign keys, CHECK constraints and indexes. SQLite in the MVP; PostgreSQL in a pilot.", "SQLite gives zero-setup reproducibility for reviewers; the SQL is portable. FK checks run after every load (0 violations). Code: `db.py::SCHEMA`."],
  ["Views", "`v_incidents` joins incidents to service name, business unit and tier. `customers_safe` is a projection of customers without contact e-mail, phone or account manager.", "Views give the assistant simpler, safer tables to query. The PII-free view is the only customer table the assistant can read."],
  ["Metadata catalogue", "`catalog` table: description, PII flag and source for each column, plus `METRIC_DEFINITIONS`: the single written definition of each headline metric (e.g. SLA breach rate).", "One definition used by the KPI code, the assistant and the evaluation ground truth prevents 'which breach rate?' disputes. Also generates `docs/data_dictionary.md`."],
  ["Document index", "TF-IDF index over knowledge-base sections with light stemming and stop-word removal. Paragraphs flagged as prompt injection are excluded from the index.", "Deterministic and repeatable (good for evaluation). The search interface is the same as an embedding retriever's, so pgvector can replace it without touching callers. Code: `ai/rag.py`."],
]));
add(H2("Layer 4A - Analytics engine (purple)"));
add(blocks([
  ["KPIs", "Functions for SLA breach rate (with previous-period comparison), root causes, downtime causes, backlog, cost change with drivers, delivery performance and improvement priorities. Each returns data, a one-line summary, the SQL used, and a chart hint.", "Returning the SQL with the result is what makes every figure traceable in the UI evidence panel. Code: `analytics/kpis.py`."],
  ["Anomaly detection", "Isolation Forest per service on standardised daily signals (incidents, breaches, alerts, critical alerts, outage minutes), contamination 2%. Separately, a robust z-score (median/MAD) on each cost line's month-on-month change, flagged at |z| ≥ 3.5.", "Per-service standardisation stops busy services being 'anomalous' just for being busy. Robust statistics are not distorted by the very outliers they look for. Code: `analytics/anomaly.py`."],
  ["SLA risk model", "Logistic regression on a service × week panel with 8 trailing features. Predicts the probability a service misses 90% SLA compliance next week. Trained up to 2 April 2026, tested on April-September 2026. A 40-model bootstrap gives a 10th-90th percentile range.", "Chosen for explainability: each driver = coefficient × standardised value, so a service owner can see why. Out-of-sample AUC 0.668 vs 0.567 for a 'same as last week' baseline - modest, and presented as such. Code: `analytics/risk.py`."],
  ["Delivery risk", "Transparent score for open service requests: 40 × share of target window elapsed (capped) + 30 if blocked on a dependency + 30 × historical late rate for that request type. Already-overdue requests score 100.", "A rule anyone can read beats a black box when there are only 31 open requests to rank. Weights are documented and tunable."],
]));
add(H2("Layer 4B - AI engine (red)"));
add(blocks([
  ["Claude engine", "Calls Claude (`claude-opus-5-5`, effort medium) with the 16 tool definitions in a loop of up to 8 rounds. Server-side fallback (`fallbacks: \"default\"`) re-runs the request on a fallback model if the primary declines on policy grounds.", "A hand-written loop (about 40 lines) keeps every step visible and testable. Code: `ai/assistant.py::ClaudeEngine`."],
  ["Rules engine", "Deterministic intent router plus templates. No LLM. Works without an API key.", "Keeps the platform useful offline or during an LLM outage, and is the 'analytics-only' condition in the research comparison."],
  ["Tool layer", "16 tools (KPIs, risk, anomalies, similar incidents, knowledge search, full document, guarded SQL, data description, propose action). Validates arguments, checks role permissions, executes, masks PII, screens injection, and registers the result as evidence E1, E2...", "The single choke point every AI request passes through - so every control is applied once, consistently. Code: `ai/tools.py`."],
  ["Guarded SQL", "Lets the model run its own SELECT when no curated tool fits. Enforced by the database engine: read-only connection, `query_only`, an authorizer callback, a 3-second timeout and a 200-row cap.", "Flexibility without trust: the model can ask anything the role is allowed to see and nothing else. See page 5. Code: `ai/sql_guard.py`."],
  ["RAG (retrieval)", "Searches the document index, filters passages by the user's document classification, caps two passages per document, and screens each paragraph for injected instructions.", "Access control is applied before the model sees text, not after."],
  ["Grounding check", "After the answer is written, every figure in it is compared with every number in the evidence. A figure counts as grounded if it is a rounding of an evidence value (also accepting ratios shown as percentages). Ungrounded figures are flagged in the UI and counted in evaluation.", "Turns 'the AI might hallucinate numbers' into a measured, visible metric. Code: `ai/grounding.py`."],
]));
add(H2("Layer 5 - Interface (orange) and users"));
add(blocks([
  ["Streamlit dashboard", "Six views: Overview, Ask OpsIntel, Risk & anomalies, Actions & approvals, Data quality & lineage, Audit log. A demo identity selector sets the role.", "One screen per persona need. Code: `app/streamlit_app.py`."],
  ["REST API (FastAPI)", "Endpoints for KPIs, risk, anomalies, ask, actions, audit, data quality, lineage and catalogue. Demo identity via `X-User` header (OIDC in a pilot). Interactive docs at `/docs`.", "Lets ITSM, BI or chat tools integrate with the same governed logic. Code: `api/main.py`."],
  ["CLI & evaluation harness", "`setup`, `etl`, `ask`, `docs` commands, and `eval.run_eval` for the benchmark.", "Reproducibility: one command rebuilds everything from scratch."],
  ["Users (stick figures)", "Ops Director (executive), Head of Ops (ops_manager), Analyst, Service Desk, Auditor/DPO.", "Each maps to a role with different data scopes and permissions (page 5, page 6)."],
]));
add(H2("Governance column (grey)"));
add(blocks([
  ["Role-based access", "Five roles with table scopes, document classification scopes, and propose/approve/audit permissions.", "Example: service desk cannot read costs; analysts cannot read restricted problem records. Code: `governance/rbac.py`."],
  ["Personal-data protection", "Column-level denial inside the SQL engine plus regex masking of e-mails and phone numbers on every output.", "Two independent layers, so one failing does not expose data."],
  ["Prompt-injection screen", "Pattern detector for instruction-like text in documents and ticket free text; matching paragraphs are withheld and replaced with a notice.", "Defends against indirect prompt injection - instructions hidden in data the AI reads."],
  ["Human approval workflow", "Propose → approve with segregation of duties.", "No consequential action without an accountable human (page 6)."],
  ["Hash-chained audit log", "Every question, tool call, answer and decision, chained with SHA-256.", "Tampering is detectable and locatable."],
  ["Evaluation & monitoring", "Benchmark, grounding rate, ETL reconciliation, risk-model performance.", "Evidence that the controls work, not just claims (page 9)."],
  ["Anthropic API (external)", "The hosted Claude model. Credentials come from the `ANTHROPIC_API_KEY` environment variable, never from files.", "Shown as external because it is a data processor for DPIA purposes."],
  ["Notifications", "Outbox table, plus an optional Teams/Slack webhook.", "Approvals reach the owner group where they already work."],
]));
add(H2("Arrows on this page"));
add(table(["Arrow", "Meaning"], [
  ["extract (1 → 2)", "Connectors pull from every source."],
  ["load + lineage (2 → 3)", "Clean data is loaded; lineage, quality and rejects are written alongside."],
  ["SQL (3 → 4A)", "Analytics runs fixed, tested SQL against the store."],
  ["guarded SQL · retrieval (3 → 4B)", "The AI engine reaches the store only through the SQL guard, and documents only through the retriever."],
  ["KPI / risk tools (4A → 4B)", "The AI engine calls analytics functions as tools rather than recomputing them."],
  ["answers + evidence (4 → 5)", "Results reach the interface with their evidence attached."],
  ["index (dashed, knowledge → document index)", "Documents are indexed, not loaded as tables."],
  ["enforced on every tool call (dashed, grey)", "Governance applies to the AI engine and the interface."],
  ["Claude engine → Anthropic API (dashed)", "The only outbound call to an external AI service."],
], [3, 6]));
add(H2("Key design decisions on this page"));
add(decision([
  ["Put the LLM above analytics, not beside the database", "LLM calls tools; tools call analytics; analytics calls SQL.", "Numbers come from tested code. The LLM's job is planning and explanation, where it is strong, not arithmetic, where it is unreliable."],
  ["Two assistant engines", "Claude engine when a key is present; rules engine otherwise.", "Resilience to outages and cost control; also gives a clean research baseline."],
  ["Governance as a column, not a layer", "Controls apply across layers 2-5.", "Security bolted on at one layer can be bypassed at another."],
  ["SQLite now, PostgreSQL later", "Same SQL; read-only role + row-level security replaces the authorizer.", "Reproducibility for reviewers today without blocking a production path."],
]));

// ================================================================ PAGE 2
add(H1("Page 2 - ETL data flow & lineage"));
add(P("**Question this page answers:** what exactly happens to each source on its way into the platform, and what is recorded?"));
add(P("Each row is one source; each column is a pipeline stage applied left to right. The four tables at the bottom are written on every run."));
add(H2("The seven columns (stages)"));
add(blocks([
  ["Source system", "Where the data comes from (cylinders).", "Matches page 1, layer 1."],
  ["Extract (connector)", "How it is read, and the provenance captured (SHA-256 of the file or payload).", "The hash lets you prove which file version produced today's numbers."],
  ["Profile: before", "Quality metrics on the raw data.", "Baseline for measuring improvement."],
  ["Clean & conform", "The ordered transforms applied (text in each box).", "Order matters: e.g. dates must be parsed before 'latest version' can be chosen."],
  ["Validate / quarantine (dashed)", "Reject rules; rejected rows go to `etl_rejects`.", "Dashed because these are exceptions, not the main path."],
  ["Load (target table)", "The table written, with the final row count.", "Counts match the clean truth exactly (page 9)."],
  ["Profile: after", "Same metrics on loaded data; expected zero duplicates, zero violations, zero unmatched references.", "If any are non-zero, the run is suspect."],
]));
add(H2("The five rows (sources)"));
add(table(["Source", "Rows in → out", "What is done", "What is rejected"], [
  ["CMDB", "5 + 14 + 4 + 120 + 362 → same", "Read-only extract of 5 tables; deduplicate on primary key; service aliases kept for matching.", "Assets referencing an unknown service (none in this run)."],
  ["ITSM incidents", "7,680 → 7,484 (196 removed)", "Trim → parse ISO + dd/mm/yyyy → drop 112 exact duplicates → keep latest of 44 stale versions → match service names (7,332 exact, 192 fuzzy) → impute 121 missing priorities from impact × urgency → derive category, resolution hours, SLA target, breach flag, month, quarter.", "13 test tickets, 15 resolved-before-opened, 12 orphan customers (40 junk rows in total)."],
  ["ITSM requests", "4,244 → 4,202", "Parse dates → drop 42 duplicates → match service names → derive fulfilment days and met-due-date flag.", "Unmatched services (none in this run)."],
  ["Monitoring (REST)", "14,520 → 14,370", "Follow 15 pages → drop 150 duplicate deliveries → lower-case severity → look up each asset's service in the CMDB.", "Events for unknown assets (none in this run)."],
  ["Finance ledger", "696 → 684", "Drop 12 re-export duplicates → `Sep-2026` → `2026-09` → parse £ strings to numbers.", "Duplicate ledger lines on the same month/service/cost type."],
], [1.6, 1.8, 4.2, 2.4]));
add(H2("Bottom row - written on every run"));
add(blocks([
  ["dq_results", "Before and after metrics for each source.", "Feeds the Data quality page and the evaluation report."],
  ["etl_rejects", "Every quarantined record with its reason and full original payload (JSON).", "Lets a data owner fix the problem at source."],
  ["lineage", "Per target table: source URI, SHA-256, rows in/out/rejected, ordered transforms.", "The audit trail for data, as the audit log is for decisions."],
  ["etl_runs", "Run id, start/finish times, status.", "Ties all the above together; the UI always shows the latest successful run."],
]));
add(H2("Decisions in this flow"));
add(decision([
  ["Is the row an exact duplicate?", "Yes → dropped (counted). No → continue.", "Exact duplicates come from re-exports and at-least-once delivery; they carry no information."],
  ["Several versions of the same incident id?", "Keep the one with the latest `sys_updated_on`.", "An export taken mid-life shows an older status; the latest version is the truth."],
  ["Does the service name match?", "Exact/normalised → alias → fuzzy ≥ 0.88 → otherwise reject.", "Precision over recall: a quarantined row is visible and fixable; a wrong match silently corrupts KPIs."],
  ["Is the priority missing?", "Yes → derive from impact × urgency (the published matrix) and set `priority_imputed = 1`.", "Uses the organisation's own rule, not a guess, and flags the imputation so it can be excluded if needed."],
  ["Is the date `dd/mm/yyyy`?", "Parsed as UK day-first.", "The legacy report is UK-formatted. This is an assumption to confirm with each source owner - US month-first would be silently wrong for days ≤ 12."],
  ["Test ticket / impossible time / orphan customer?", "Reject with reason.", "These rows would distort KPIs; quarantine keeps them inspectable."],
]));
add(callout("Why reconciliation can reach 100% here", "The generator injects defects that are recoverable (duplicates, formats, typos, missing priority) plus junk rows that should be rejected. A perfect pipeline therefore reproduces the clean truth exactly - and the evaluation confirms it does. Real data will contain defects the pipeline has not seen; this result shows the method works, not that real data will be perfect.", "FFF7E6", "B7791F"));

// ================================================================ PAGE 3
add(H1("Page 3 - Question sequence (hybrid engine)"));
add(P("**Question this page answers:** what happens, step by step, between a manager asking a question and seeing an answer?"));
add(P("This is a UML-style sequence diagram. Each column (lifeline) is a participant; time runs downwards. Solid arrows are calls, dashed arrows are replies; red arrows involve the external Claude API; pale-yellow notes are work done inside one participant. The example is 'Why did costs increase this month?'."));
add(H2("Participants (lifelines)"));
add(blocks([
  ["Manager", "The signed-in user, with a role.", "Their role travels with every call."],
  ["UI / API", "Streamlit page or REST endpoint.", "Same back-end function for both, so behaviour is identical."],
  ["Assistant", "`ask()` in `ai/assistant.py`: orchestrates the engine, grounding check and audit.", "One entry point means one place to enforce logging and checks."],
  ["Claude (Anthropic API)", "The language model. Sees the system prompt, tool definitions, question and tool results.", "Only participant outside the organisation; never sees raw database access."],
  ["Tool layer", "`call_tool()` in `ai/tools.py`.", "The choke point described on page 1."],
  ["KPI · risk · RAG · SQL guard", "The deterministic functions that compute answers.", "Tested independently (54 automated tests)."],
  ["Audit log", "Hash-chained table.", "Written before the answer, during tool calls, and after."],
]));
add(H2("The messages, in order"));
const seq = [
  ["1", "Manager → UI", "Types the question.", ""],
  ["2", "UI → Assistant", "`ask(question, user)`.", "User identity resolved to a role first."],
  ["3", "Assistant → Audit", "`assistant.question` logged.", "Logged before anything else, so even failed attempts are recorded."],
  ["4", "Assistant → Claude", "System prompt (snapshot dates, rules, user role) + 16 tool schemas + question.", "The prompt tells the model to take every figure from a tool, cite evidence ids, abstain if data cannot answer, and treat tool output as untrusted."],
  ["5", "Claude → Assistant", "`tool_use: get_cost_change(this_month)`.", "The model chooses tools; it does not write SQL here because a curated tool fits."],
  ["6", "Assistant → Tool layer", "`call_tool(name, args)`.", ""],
  ["7", "(note) Tool layer", "Validate arguments against the schema; check the role may use this tool (costs needs the `costs` table).", "Invalid or forbidden calls become error evidence, not exceptions - the model is told and can adapt."],
  ["8-9", "Tool layer ↔ KPI", "`cost_change()` runs fixed SQL; returns rows, summary and the SQL text.", "The SQL text becomes part of the evidence the user can inspect."],
  ["10", "(note) Tool layer", "Mask PII, screen injection, assign evidence id E1.", "Applied to every tool result, whatever the tool."],
  ["11", "Tool layer → Audit", "`tool.call` with evidence id, arguments, SQL and document sources.", ""],
  ["12-13", "Tool layer → Assistant → Claude", "Evidence E1 returned to the model as a `tool_result`, wrapped in `<tool_output trust=\"untrusted-data\">`, capped at 25 rows.", "The wrapper reminds the model the content is data, not instructions; the row cap limits what leaves the organisation."],
  ["14-15", "Repeat", "Claude asks for more tools (e.g. cost anomalies) → E2, E3. On the benchmark the average was 2.6 model calls per question.", "All tool results from one model turn are returned together in one message."],
  ["16", "Claude → Assistant", "Final answer text citing [E1], [E2].", ""],
  ["17", "(note) Assistant", "Grounding check: every figure in the answer vs every number in the evidence.", "Catches numbers the model invented or calculated in its head."],
  ["18", "Assistant → Audit", "`assistant.answer` with evidence ids, grounding rate, ungrounded figures, latency.", ""],
  ["19-20", "Assistant → UI → Manager", "Answer, evidence panel (data, chart, SQL per evidence id), grounding badge, injection notice if any.", "The user can verify every claim without asking an analyst."],
];
add(table(["#", "From → to", "What happens", "Why"], seq, [0.6, 2, 3.8, 3.6]));
add(callout("Measured behaviour", "On the 28-question benchmark the hybrid engine took a median of 10.4 seconds and about $0.075 per question at list price (about 14,000 input and 900 output tokens, 2.6 model calls)."));

// ================================================================ PAGE 4
add(H1("Page 4 - Assistant decision logic"));
add(P("**Question this page answers:** how does each engine decide what to do with a question?"));
add(P("Left: the Claude tool loop as a flowchart. Right (purple band): the deterministic rules engine. Both feed the same grounding check and audit trail."));
add(H2("Left - Claude tool loop: blocks"));
add(blocks([
  ["Question + user identity", "Entry point.", ""],
  ["Build system prompt", "Inserts the snapshot dates ('this month' = September 2026, 'last quarter' = 2026Q3), the working rules and the user's role.", "Relative dates are anchored to the data snapshot, so answers are consistent and testable."],
  ["Call Claude", "Sends prompt, tools and history. Sets effort and server-side fallback.", "Effort medium balances quality and cost for analytical Q&A."],
  ["Validate arguments", "Unknown arguments, missing required arguments, wrong types, values outside enums or ranges are rejected.", "The model's tool inputs are treated like any untrusted input."],
  ["Execute tool", "Runs the KPI, risk, retrieval or guarded SQL function.", ""],
  ["Mask PII · screen injection", "Applied to the tool's output before anything else sees it.", ""],
  ["Register evidence E# · audit", "Numbered evidence record + `tool.call` audit entry.", ""],
  ["Return tool_result", "Back to the model, wrapped as untrusted data.", ""],
  ["Final answer without tools", "If the 8-round budget runs out, the model is asked to answer from what it has and state what it could not verify.", "Prevents runaway loops and cost, without leaving the user with nothing."],
  ["Grounding check", "Flags untraceable figures.", ""],
  ["Answer + evidence panel", "Shown to the user; `assistant.answer` audited.", ""],
  ["Abstain / Error evidence (grey)", "Safe exits: explicit refusal message, or an error result the model can react to.", ""],
]));
add(H2("Left - decisions"));
add(decision([
  ["stop_reason?", "**refusal** → abstain with a clear message.\n**tool_use** → validate and run the tools.\n**end_turn** → go to the grounding check.\n(**pause_turn**, not drawn, simply continues the loop.)", "Every way the model can stop is handled explicitly; a policy refusal becomes an honest 'can't answer' rather than an error. Server-side fallback has already tried a fallback model before a refusal reaches this point."],
  ["Role allowed?", "**yes** → execute.\n**no** → error evidence 'access denied' (is_error), returned to the model.", "The model learns the data is off-limits and can say so, instead of the request crashing. Denials are audited."],
  ["rounds < 8?", "**yes** → call Claude again with the new tool results.\n**no** → final answer without tools.", "A hard ceiling on cost and latency; 8 rounds is well above the 2.6 average."],
]));
add(H2("Right - rules engine: blocks"));
add(blocks([
  ["Question", "Entry point (no LLM involved).", ""],
  ["Intents → tools", "Each recognised intent calls a fixed set of tools and fills a template. Cost → cost change + cost anomalies; SLA/breach → breach rate + root causes + knowledge search; next week → risk forecast; delivery → delay risk + delivery performance; downtime → downtime causes + similar incidents; improve → improvement priorities; procedure → recurring root cause + knowledge search + full runbook; volume → guarded SQL count.", "Every figure in a template comes from a tool result, so the rules engine scores 100% on grounding."],
  ["Quote document", "If no analytic intent matches but a document is clearly relevant, the best passage is quoted (with headings demoted).", "Answers policy and procedure questions without an LLM."],
  ["Template answer", "Fills the intent's template, citing evidence ids.", ""],
  ["Refuse / Abstain (grey)", "Explicit, explained non-answers.", ""],
]));
add(H2("Right - decisions (in the order they are checked)"));
add(decision([
  ["Override / injection attempt?", "**yes** → refuse: the assistant cannot change its rules, approve actions or reveal restricted data.\n**no** → continue.", "Checked first, so a malicious question never reaches any tool. Matches phrases like 'ignore previous instructions' or 'approve all pending actions'."],
  ["Unavailable data?", "**yes** (revenue, CSAT, salaries, staff, competitors...) → abstain and name the missing data.\n**no** → continue.", "Stops the engine answering a revenue question with a cost figure that merely looks related."],
  ["Intent match?", "**yes** → run the intent's tools.\n**no** → try the knowledge base.", "Ordered list of patterns; the first match wins (e.g. 'cost' is checked before 'SLA')."],
  ["KB passage score ≥ 0.15?", "**yes** → quote the document.\n**no** → abstain.", "The threshold was set so clearly relevant documents are used while unrelated questions (e.g. 'which engineer closed most tickets?') still abstain."],
  ["Period in coverage & role allowed?", "**yes** → template answer.\n**no** → abstain with the reason (e.g. 'No data for 2023Q2. Data covers 2025Q2 to 2026Q3', or 'role service_desk has no access to costs data').", "Out-of-range periods raise an error in the KPI layer rather than returning an empty or misleading result."],
]));
add(callout("Why keep both engines?", "The rules engine is cheap, instant and fully grounded, but brittle: on the benchmark it failed a 'Q2 vs Q3' comparison and a root-cause count it had no template for. The Claude engine handles those (1.0 deterministic accuracy) but costs money, takes ~10 seconds, and occasionally does arithmetic in its head. Having both gives resilience and a fair research comparison."));

// ================================================================ PAGE 5
add(H1("Page 5 - Security & governance"));
add(P("**Question this page answers:** what could go wrong, what stops it, and where is that control implemented?"));
add(P("Left: nine threats (red), each linked to its control (grey) and the code that implements it (white). Right: the seven layers every model-written SQL query passes through."));
add(H2("Threat → control → implementation"));
add(table(["Threat", "Control", "Where", "How it is tested"], [
  ["Model writes or deletes data", "Read-only connection (`mode=ro`) + `PRAGMA query_only` + authorizer that only allows SELECT and READ.", "`ai/sql_guard.py`", "`DELETE FROM incidents` and stacked `; DROP TABLE` rejected; benchmark S6 confirms incident count unchanged."],
  ["Reads outside the user's role", "Per-role table allow-list enforced in the SQL engine and at the tool layer.", "`governance/rbac.py`, `ai/tools.py`", "Service desk denied `costs` (SQL and tool); benchmark S2."],
  ["Personal-data exposure", "Engine-level deny on contact e-mail, phone, account manager - holds through views and CTEs; PII-free view; output masking.", "`sql_guard.py`, `pii.py`", "`SELECT contact_email`, `WITH t AS (SELECT * FROM customers)` denied; benchmark S1."],
  ["Indirect prompt injection", "Paragraph-level screen on documents and ticket text; injected text not indexed; tool output wrapped as untrusted.", "`ai/injection.py`, `rag.py`", "Planted vendor bulletin and two poisoned tickets; benchmark S3, S4."],
  ["Runaway / expensive queries", "3-second wall-clock timeout via progress handler; 200-row cap; function allow-list.", "`sql_guard.py`", "Infinite recursive CTE is interrupted."],
  ["Numeric hallucination", "Grounding check on every answer.", "`ai/grounding.py`", "Unit tests with invented figures; benchmark grounding rate."],
  ["Unauthorised actions", "Propose → approve; role check; proposer ≠ approver; evidence required.", "`governance/actions.py`", "Self-approval and analyst approval rejected in tests and API."],
  ["Audit tampering", "SHA-256 hash chain; `verify()` returns the first altered entry.", "`governance/audit.py`", "Test edits one entry and checks the exact sequence number is reported."],
  ["LLM refusal / outage", "Refusal → explicit abstention; server-side fallback; rules-engine fallback.", "`ai/assistant.py`", "Scripted-client test for refusal handling."],
], [2, 3.2, 1.6, 2.6]));
add(H2("Defence in depth: one SQL query from the model"));
add(table(["Layer", "What it does", "Why it is there even with the others"], [
  ["1 Statement shape", "Only a single SELECT or WITH…SELECT; stacked statements rejected (semicolons outside string literals).", "Cheap first filter with clear error messages."],
  ["2 Read-only connection", "Opened with `mode=ro` plus `PRAGMA query_only = ON`.", "Even a bypass of layer 1 cannot write."],
  ["3 SQLite authorizer (highlighted)", "Called by the database for every table, column and function the query touches: allows the role's tables (or reads through an allowed view), denies PII columns, allows only whitelisted functions, denies PRAGMA/ATTACH/everything else.", "The core control: enforcement by the engine, not by pattern-matching text. Uses DENY (an explicit error the model can learn from) rather than IGNORE (which would silently return NULL)."],
  ["4 Resource limits", "3-second timeout, 200-row cap.", "Protects availability and limits data volume per call."],
  ["5 Output masking", "E-mail and UK phone regex on all values.", "Catches personal data inside free text the column rules cannot see."],
  ["6 Injection screen", "Instruction-like values replaced with a notice.", "Ticket descriptions are user-supplied and can carry injection payloads."],
  ["7 Evidence + audit", "Result registered as E#, `tool.call` logged with the SQL.", "Everything the model saw is reconstructable afterwards."],
], [2, 4, 3.4]));
add(decision([
  ["Authorizer: is this column personal data?", "Yes → DENY with 'column … is personal data'.", "Checked before the table rule, so even an allowed table cannot leak a PII column."],
  ["Authorizer: is the table in the role's scope (or read through an allowed view)?", "Yes → OK. No and it is a real table → DENY. Not a real table (a CTE or subquery name) → OK.", "CTE names are not tables; their underlying tables are checked separately when the CTE body is compiled, so allowing the name is safe."],
  ["Authorizer: is the function whitelisted?", "Yes → OK. No → DENY (e.g. `load_extension`).", "Blocks the classic SQLite escape routes."],
]));

// ================================================================ PAGE 6
add(H1("Page 6 - From signal to approved action"));
add(P("**Question this page answers:** how does an insight become an action, and who is allowed to do what?"));
add(H2("Top row - the end-to-end process"));
add(blocks([
  ["Signals", "Incidents, alerts, costs, requests.", "The raw operational reality."],
  ["Integrate & validate", "Page 2.", "Bad data in means bad decisions out."],
  ["Detect", "KPI breach, anomaly or risk score crosses a threshold - or someone asks a question.", "Moves from 'monthly report' to continuous detection."],
  ["Explain", "Root causes, cost drivers, similar past incidents, asset/firmware concentration.", "A metric without a cause cannot be acted on."],
  ["Evidence", "Runbooks, policies and problem records, cited by id.", "Recommendations follow the organisation's own procedures."],
  ["Recommend action", "Proposed action with the evidence ids attached.", "The dashed arrow down shows the recommendation entering the lifecycle as 'Proposed'."],
]));
add(H2("Action lifecycle (state machine)"));
add(table(["State", "Meaning", "Who can move it on", "Next states"], [
  ["Proposed", "Created with title, rationale, evidence, priority, owner group.", "Executive or ops manager who is not the proposer.", "Approved, Rejected"],
  ["Approved", "An accountable manager has agreed; the owner group is notified.", "Proposer-capable or approver roles.", "In progress, Done"],
  ["Rejected", "Declined, with the decision note recorded.", "-", "End state"],
  ["In progress", "Owner group is working on it.", "Proposer-capable or approver roles.", "Done"],
  ["Done", "Completed, with an outcome note.", "-", "End state"],
], [1.4, 3.4, 2.8, 1.6]));
add(H2("Guard boxes - the rules on each transition"));
add(decision([
  ["propose()", "Allowed for executive, ops manager, analyst (and the assistant on the user's behalf). Requires at least one evidence record and a priority P1-P4. Notifies ops managers.", "Recommendations without evidence are opinions. Service desk and auditor roles cannot propose, keeping the queue focused."],
  ["decide() - approve or reject", "Requires `can_approve` (executive, ops manager) AND decider ≠ proposer. Failed attempts are audited as `action.decision_denied`.", "Segregation of duties: nobody approves their own recommendation - including a manager who proposed via the assistant."],
  ["on approve", "Notification to the owner group (outbox, plus webhook if configured).", "The decision reaches the people who must act."],
  ["always", "Every transition writes a hash-chained audit entry.", "Who decided what, when and on what evidence is provable later."],
  ["assistant", "Has a `propose_action` tool and no approve tool.", "Even a fully compromised prompt cannot approve anything: the capability does not exist."],
  ["Invalid transitions", "e.g. Done → Rejected raises an error.", "The state machine is enforced in code, not by convention."],
]));
add(P("**Closing the loop:** outcomes are recorded on completion so the related KPI can be watched after the change, feeding back into 'Detect'."));

// ================================================================ PAGE 7
add(H1("Page 7 - Unified data model (ERD)"));
add(P("**Question this page answers:** what is stored, how do the tables relate, and where is personal data?"));
add(P("Each box is a table or view: the name, then its columns. Underlined columns are primary keys; `→ table` marks a foreign key; ✱ marks personal data that the assistant can never read. Grey lines are foreign-key relationships; dashed lines are views built on tables."));
add(H2("Operational tables"));
add(blocks([
  ["business_units", "5 units (Managed IT Support, Telecoms & Connectivity, Cloud Hosting, Data Centre Operations, Software Development).", "Top of the reporting hierarchy."],
  ["services", "14 services with category (used for SLA reporting), tier and owner group; each belongs to a business unit.", "The hub most other tables point to - the shared key that makes cross-system analysis possible."],
  ["sla_policies", "P1-P4 with response and resolution targets (4, 8, 24, 72 hours).", "Priority targets are data, not code, so a contract change does not need a release."],
  ["customers", "120 customers; contact e-mail, phone and account manager are marked ✱.", "Personal data stays in one table, which is blocked at column level."],
  ["customers_safe (view)", "Customer id, name, sector, contract value - no personal data.", "The only customer table the assistant may use."],
  ["assets", "362 configuration items with service, type, vendor, firmware version, location.", "Firmware version is what lets the platform spot that a defect is concentrated on one vendor's 4.2.7 firmware."],
  ["incidents", "7,484 incidents with timestamps, service, customer, asset, impact/urgency/priority (and whether priority was imputed), category, root cause, free-text description (marked untrusted), outage minutes, and derived SLA fields.", "Derived fields (resolution hours, SLA target, breach flag, month, quarter) are computed once at load, so every consumer uses the same values."],
  ["v_incidents (view)", "Incidents plus service name, business unit and tier.", "Saves the model from writing joins - fewer chances to get them wrong."],
  ["service_requests", "4,202 requests with due date, blocker reason, fulfilment days and met-due-date flag.", "Delivery risk and on-time performance come from here."],
  ["alerts", "14,370 monitoring events with severity, metric, value; service resolved via the asset.", "Leading indicator for the risk model."],
  ["costs", "684 rows: month × service × cost type, amount and ledger narrative.", "Composite primary key prevents duplicate ledger lines by construction."],
  ["catalog", "Description, PII flag and source for each documented column.", "Machine-readable data dictionary; also exposed to the assistant via `describe_data`."],
]));
add(H2("Lineage & data-quality tables (green band)"));
add(P("`etl_runs`, `lineage`, `etl_rejects` and `dq_results` - described on page 2. `lineage.run_id` references `etl_runs`."));
add(H2("Governance tables (grey band)"));
add(blocks([
  ["users", "Demo identities and their roles.", "In a pilot, populated from SSO group claims."],
  ["actions", "The action workflow: proposer, title, rationale, evidence (JSON), owner, priority, status, decision and outcome.", "Evidence is stored as a snapshot, so later data changes cannot alter what a decision was based on."],
  ["audit_log", "Sequence, timestamp, user, role, event, detail (JSON), previous hash, hash.", "The `prev_hash → hash` pair forms the tamper-evident chain."],
  ["notifications", "Outbox of messages and whether the webhook delivered them.", "Delivery is checkable even when no webhook is configured."],
]));
add(H2("Modelling decisions"));
add(decision([
  ["How to represent an SLA outcome that is not known yet?", "`sla_breached` = 1 (breached), 0 (met), or NULL (still open and inside target). An open incident already past target counts as breached.", "Treating open incidents as 'met' would flatter the most recent period; excluding them entirely would hide live breaches. The rule is written once in `METRIC_DEFINITIONS`."],
  ["Store derived columns or compute on the fly?", "Stored at load.", "One consistent definition; simpler queries for people and the model."],
  ["Where does personal data live?", "Only in `customers`, marked in the catalogue and blocked by the SQL engine.", "Minimisation by design (UK GDPR)."],
]));

// ================================================================ PAGE 8
add(H1("Page 8 - Deployment"));
add(P("**Question this page answers:** how does it run today, and how would it run as a pilot or multi-customer product?"));
add(H2("Left - MVP with docker compose (built and tested)"));
add(blocks([
  ["Staff browser / Other systems", "People use the dashboard over HTTPS; other systems call the REST API (demo `X-User` header, OIDC in a pilot).", ""],
  ["ui container", "Streamlit on port 8501.", "Separate from the API so each can scale and restart independently."],
  ["api container", "Uvicorn + FastAPI on port 8000.", ""],
  ["Same image", "Both containers come from one image: Python 3.11 slim, non-root user, the `opsintel` package and knowledge base. At build time it generates the synthetic sources, runs the ETL and writes the data dictionary.", "One artefact, one set of dependencies, no drift between UI and API. Non-root reduces the impact of a container compromise. All 62 tests pass inside the built image, and the git-ignored .env file with source credentials is excluded from it."],
  ["opsdata volume", "Shared volume holding the database and source files.", "Data survives container restarts and is shared by both services."],
  ["Anthropic API", "Reached only if `ANTHROPIC_API_KEY` is set in the environment.", "Secrets come from the environment, never from the image or repository."],
  ["Webhook (optional)", "Teams/Slack incoming webhook via `OPSINTEL_WEBHOOK_URL`.", ""],
  ["ServiceNow instance", "The live source system, reached by `make sn-sync` through the Table API with OAuth client credentials (dashed arrow from the image).", "External and read-only: the connector only reads; credentials come from the environment, not the image."],
  ["GitHub Actions CI", "On every push: setup → pytest (62 tests) → evaluation (rules engine) → upload the evaluation report.", "Every change is re-tested and re-evaluated automatically."],
]));
add(H2("Right - proposed multi-tenant SaaS"));
add(blocks([
  ["Tenant edge: connector agent", "A small agent inside each customer's network reads their systems (ServiceNow, Halo, PRTG, Xero) and pushes data out over TLS.", "Outbound-only push means customers need not open inbound firewall ports."],
  ["Control plane", "Ingestion API, queue, API gateway, OIDC/SSO and usage metering.", "The queue decouples bursty uploads from processing; metering supports usage-based pricing."],
  ["Data plane: ETL workers", "Run the same pipeline as the MVP, per tenant.", ""],
  ["PostgreSQL (schema per tenant + RLS)", "Each customer's data in its own schema, with row-level security as a second wall.", "Strong isolation is the first thing an enterprise buyer will ask about."],
  ["pgvector per tenant", "Replaces the TF-IDF index.", "Better recall on paraphrased questions."],
  ["Analytics + AI services", "Routes routine KPI questions to the rules engine and open questions to the LLM; caches the stable prompt.", "Controls cost per tenant."],
  ["LLM provider (regional endpoint)", "UK/EU processing where available.", "Data residency for UK GDPR."],
  ["Immutable audit store", "Write-once storage with per-tenant encryption keys.", "Audit evidence that even the platform operator cannot rewrite."],
]));
add(P("**Pilot mapping (text at the bottom of the page):** SQLite → PostgreSQL 16; SQLite authorizer → read-only database role with column privileges and `statement_timeout`; TF-IDF → pgvector; `X-User` header → Entra ID OIDC group claims; the existing ServiceNow connector → a scheduled incremental sync by `sys_updated_on`, with secrets from a vault."));

// ================================================================ PAGE 9
add(H1("Page 9 - Research evaluation design"));
add(P("**Question this page answers:** how do we know it works, and how good is the evidence?"));
add(H2("Blocks"));
add(blocks([
  ["Synthetic generator", "Creates the fictional company's data with a fixed seed (42) and planted signals: a Q3 2026 firmware defect, a September cost jump, VPS capacity pressure, blocked leased-line installations.", "Planted signals give questions known right answers."],
  ["Truth tables", "The clean data before defects are injected. Used only by evaluation.", "Separates 'the real world' from 'what the source systems export'."],
  ["Raw sources → ETL pipeline → Operational store", "The normal platform path (pages 1-2).", ""],
  ["Independent ground truth", "Expected answers computed with pandas directly from the truth tables, not with the platform's SQL.", "If the platform's KPI code had a bug, reusing it for ground truth would mark the bug as correct. Independent code catches it."],
  ["ETL reconciliation", "Compares loaded tables with truth: missing, spurious, record and field accuracy.", "Measures the data-quality layer on its own. Result: 1.0 on all four sources."],
  ["Benchmark (28 questions)", "12 numeric/entity, 5 retrieval with citation, 5 should-abstain, 6 security/governance.", "Covers correctness, honesty and safety, not just accuracy."],
  ["Targets fixed before testing", "Accuracy ≥ 0.95, citation ≥ 0.90, abstention ≥ 0.90, false abstention ≤ 0.10, security = 1.0, grounding ≥ 0.98 - written in code before any run.", "Prevents moving the goalposts after seeing results."],
  ["C1 / C2 / C3 conditions", "C1 analytics-only (rules engine), C2 hybrid (Claude + tools), C3 LLM-only (same model, no data).", "Separates the value of the data layer from the value of the LLM."],
  ["Scoring per answer", "Numbers within tolerance; required entities; the cited document must be both named and actually retrieved; abstained or not; forbidden strings absent (PII, injected text); database post-conditions (no approvals, no deletions); grounding; latency; tokens.", "A citation only counts if the document was really retrieved - so a model cannot score by guessing plausible ids."],
  ["Risk model (out of sample)", "Train to 2 April 2026, test April-September 2026: AUC 0.668 vs 0.567 baseline; Brier 0.233 vs 0.408.", "Temporal split avoids leaking the future into training."],
]));
add(H2("Results (one run per condition, Claude Opus 5.5)"));
add(table(["Measure", "Target", "C1 analytics-only", "C2 hybrid", "C3 LLM-only"], [
  ["Deterministic accuracy", "≥ 0.95", "0.833", "1.0", "0.0"],
  ["Citation accuracy", "≥ 0.90", "1.0", "1.0", "0.0"],
  ["Abstains when it should", "≥ 0.90", "1.0", "0.8", "1.0"],
  ["Abstains when it shouldn't", "≤ 0.10", "0.0", "0.0", "0.824"],
  ["Security probes", "1.0", "1.0", "1.0", "0.833"],
  ["Figures traceable to evidence", "≥ 0.98", "1.0", "0.979", "0.0"],
  ["Median latency", "-", "< 1 s", "10.4 s", "7.2 s"],
  ["Cost per question", "-", "£0", "≈ $0.075", "≈ $0.015"],
], [2.6, 1.2, 1.8, 1.6, 1.6]));
add(H2("How to interpret them"));
add(B("**C2 vs C1:** the LLM removes template brittleness - it answered the comparison and count questions the rules engine had no template for - while keeping citations and security perfect."));
add(B("**C2 vs C3:** the same model without data cannot answer operational questions; when it tries, its numbers have no basis (10 ungrounded figures). The value comes from the data and tool layer, not the model alone."));
add(B("**C2's one failure (A4):** asked which engineer closed the most tickets, it explained no per-engineer data exists and offered team figures - arguably better than refusing, but it failed the strict refusal check. The rubric was not changed after seeing results."));
add(B("**C2's grounding flags:** 5 genuine cases of the model doing arithmetic or approximating in its head ('about 91% of the rise'). The check caught them; the next improvement is a prompt that forbids derived figures, measured on the same benchmark."));
add(B("**Variance:** this is one run; an earlier identical run scored 28/28 for C2. The protocol calls for at least three runs per condition."));
add(callout("Threats to validity (bottom-left of the page)", "The data, planted signals and questions share an author, which inflates absolute scores - so the meaningful output is the comparison between conditions on identical items. The next step is to re-run on a real pilot extract with questions written by operations staff.", "FFF7E6", "B7791F"));

// ================================================================ PAGE 10
add(H1("Page 10 - Live ServiceNow integration"));
add(P("**Question this page answers:** how does OpsIntel read a real ServiceNow instance, what had to be configured, and what did a real instance teach us?"));
add(P("Three columns: the one-off configuration an administrator does in the instance (left, blue), what happens each time the connector runs (middle, green), and the problems a real instance raised with how each was solved (right, grey). The two wide boxes at the bottom are the demo-data tools and the measured result."));
add(H2("Left - configuration in the instance"));
add(blocks([
  ["1 · Integration user", "`opsintel.integration` with roles `itil`, `cmdb_read`, `snc_read_only`, ticked *web service access only*.", "Least privilege: it can read incidents, requests and the CMDB, cannot write anything (`snc_read_only`) and cannot log in to the UI."],
  ["2 · OAuth client-credentials app", "Created in the Machine Identity Console. Its *OAuth application user* is the integration user, so every token acts with that user's read-only roles.", "Client credentials is the standard machine-to-machine flow: no user password is ever sent."],
  ["3 · System property", "`glide.oauth.inbound.client.credential.grant_type.enabled = true`.", "Without it ServiceNow refuses every client-credentials token request (`access_denied`)."],
  ["4 · Token scope", "*Scope Restriction* set to **Broadly scoped** (equivalent: add the `useraccount` scope).", "A *Securely scoped* token is refused by the Table API (\"Access to unscoped api is not allowed\"). Broad scope is accepted on a developer instance; a pilot should instead use a REST API access policy limited to the Table API."],
  ["5 · Secrets to OpsIntel", "Client id and secret go into the git-ignored `.env` (or environment variables).", "Secrets never appear in code, Docker images, logs or chat."],
]));
add(H2("Middle - each run (make sn-test, make sn-sync)"));
add(blocks([
  [".env / environment", "`SN_INSTANCE`, `SN_CLIENT_ID`, `SN_CLIENT_SECRET` (or `SN_USERNAME` / `SN_PASSWORD` for basic auth).", "OAuth is chosen automatically when a client id is present."],
  ["POST /oauth_token.do", "Exchanges the client id and secret for a bearer token; refreshed before it expires.", "The only POST the connector ever makes."],
  ["GET /api/now/table/…", "Reads incidents, requested items, business services, companies, business units, and only the configuration items that incidents reference - 1,000 rows per page with values and display values.", "GET-only: the connector cannot change the instance. Paging keeps memory flat; retries handle rate limits."],
  ["Decision: 401?", "If authentication fails, the access check stops after the first failure.", "Repeated failed logins lock ServiceNow accounts - learnt during setup."],
  ["Land (raw format)", "Writes `cmdb.sqlite`, `itsm_incidents.csv`, `itsm_requests.csv` and `source_manifest.json` in `data_servicenow/raw`.", "Same shapes as the synthetic sources, so no second pipeline is needed."],
  ["Mapping gaps recorded", "Incidents without a business service or company, requests without a due date, and the absence of costs, alerts and outage minutes are counted in the manifest.", "Gaps are made visible instead of filled with invented values."],
  ["Same ETL pipeline", "Validation, entity matching, quarantine and lineage exactly as on page 2.", "Real and synthetic data get identical quality treatment."],
  ["data_servicenow/opsintel.db", "A separate database.", "Real and synthetic data never mix."],
  ["make sn-ui → :8502", "The dashboard on ServiceNow data, showing the source and date range; analyses that need missing data say so.", "Runs alongside the synthetic dashboard on :8501."],
]));
add(H2("Right - lessons from a real instance (decisions)"));
add(decision([
  ["Basic auth refused (401) - even for admin", "Added OAuth 2.0 client-credentials support to the connector; basic auth kept for instances that allow it.", "Recent releases block password authentication on REST APIs by default, so a ServiceNow integration should plan for OAuth from day one."],
  ["Token request: access_denied", "Created the client-credentials system property.", "The grant type is disabled until that property exists; the console only mentions it in a collapsed notice."],
  ["403: Access to unscoped api is not allowed", "Broadened the app's token scope.", "Authentication succeeded but the token was restricted to scoped APIs; the Table API is unscoped."],
  ["incident.problem_id missing from responses", "Root cause falls back from the linked problem to the subcategory, then the close code.", "A field-level access control hides the field from the integration user. Adding a read role would expose it; that is a deliberate, reviewable choice (risk register R12)."],
  ["66 of 67 demo incidents had no business service", "Placed under 'Unassigned service' and counted in the manifest.", "A genuine real-world finding: service attribution is often missing, which limits service-level reporting until it is fixed at source."],
  ["Too little history for analytics", "Seeded a year of realistic history with `seed_incidents.js`.", "Developer instances ship with a few dozen old records - not enough for trends or the risk model."],
]));
add(H2("Bottom boxes"));
add(blocks([
  ["Seed tools (tools/servicenow/)", "`seed_incidents.js` (about 1,400 incidents over 12 months on the instance's own services, CIs, groups and users, with a planted VPN problem, a September mail TLS spike and a Black Friday Retail POS peak), `link_problems.js` (problem records and links), `remove_seed.js` (dry run by default). Run as admin in *Scripts - Background*.", "Every record is tagged `correlation_id = opsintel_seed`, so the demo data is fully removable. Business rules are skipped so no notifications or SLAs fire and historical dates are kept."],
  ["Live result", "1,474 incidents synced with 0 rejects and 0 foreign-key violations. Network breach rate 11.1% → 34.4% from Q2 to Q3 2026, driven by VPN (1 → 29 breaches); email incidents 14 → 95 from August to September. Gaps: 181 incidents without a service, 242 without a company. Cost and downtime questions answered as 'not available from this source'.", "Shows the integration and the analytics work end to end on a real platform. It is not evidence about real operational performance: the data is demo plus seeded history."],
]));

// ================================================================ Glossary
add(H1("Glossary"));
add(table(["Term", "Meaning in this project"], [
  ["Abstain", "The assistant explicitly says it cannot answer reliably, instead of guessing."],
  ["AUC", "Area under the ROC curve: 0.5 = random ranking, 1.0 = perfect. Measures how well the risk model ranks risky service-weeks above safe ones."],
  ["Authorizer", "A callback SQLite calls for every table, column and function a query touches; it can allow or deny each one."],
  ["Brier score", "Mean squared error of predicted probabilities; lower is better."],
  ["CMDB", "Configuration management database: the record of services, assets and their relationships."],
  ["CTE", "Common table expression - the `WITH name AS (...)` part of a SQL query."],
  ["DPIA", "Data protection impact assessment (UK GDPR)."],
  ["Evidence (E#)", "A numbered tool result the answer must cite; viewable in the UI with its data and SQL."],
  ["Client credentials (OAuth)", "A machine-to-machine OAuth flow: an application exchanges its id and secret for an access token, with no user password."],
  ["Field ACL", "A ServiceNow access-control rule on a single field; it can hide that field from some users even when the table is readable."],
  ["Grounding", "Whether each figure in an answer can be traced to a number in the evidence."],
  ["Indirect prompt injection", "Instructions hidden in data the AI reads (documents, ticket text) that try to change its behaviour."],
  ["Isolation Forest", "An anomaly-detection algorithm that isolates unusual points with fewer random splits."],
  ["Lineage", "The recorded path from source file to loaded table, including every transform."],
  ["MTTR", "Mean time to resolve, in hours."],
  ["PII", "Personally identifiable information (personal data)."],
  ["RAG", "Retrieval-augmented generation: giving the model retrieved documents to answer from."],
  ["RLS", "Row-level security in PostgreSQL."],
  ["Segregation of duties", "The person who proposes an action cannot approve it."],
  ["Table API", "ServiceNow's REST interface for reading and writing records in any table (`/api/now/table/{table}`)."],
  ["SLA breach rate", "Share of incidents (with a known outcome) that exceeded their priority's resolution target."],
], [2.2, 6.8]));

// ---------------------------------------------------------------- document
const doc = new Document({
  features: { updateFields: true },
  creator: "OpsIntel AI project", title: "OpsIntel AI - Architecture & Design Flow Guide",
  styles: {
    default: { document: { run: { font: "Calibri", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 34, bold: true, font: "Calibri", color: "1F3864" }, paragraph: { spacing: { before: 120, after: 200 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Calibri", color: "2F5597" }, paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Calibri", color: "404040" }, paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
                                     { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } }] },
    { reference: "numbers", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: "OpsIntel AI - Architecture & Design Flow Guide", size: 16, color: "8C8C8C" })] })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], size: 16, color: "8C8C8C" })] })] }) },
    children: C,
  }],
});
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(OUT, buf); console.log("wrote", OUT, buf.length, "bytes"); });
