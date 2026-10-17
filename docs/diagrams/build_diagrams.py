"""Generate docs/diagrams/opsintel_architecture.drawio (one page per diagram).

    python docs/diagrams/build_diagrams.py

Open the output in diagrams.net (app.diagrams.net or the desktop app), or import it into
Lucidchart (File > Import > draw.io). Edit this script, not the .drawio file, so the
diagrams stay reproducible.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(__file__).with_name("opsintel_architecture.drawio")

# Layer colour scheme (fill, stroke) - one colour per architectural layer, used on every page.
C = {
    "source": ("#dae8fc", "#6c8ebf"),
    "integration": ("#d5e8d4", "#82b366"),
    "foundation": ("#fff2cc", "#d6b656"),
    "analytics": ("#e1d5e7", "#9673a6"),
    "ai": ("#f8cecc", "#b85450"),
    "interface": ("#ffe6cc", "#d79b00"),
    "governance": ("#f5f5f5", "#666666"),
    "external": ("#ffffff", "#999999"),
    "note": ("#fffbe6", "#d6b656"),
}
FONT = "fontFamily=Helvetica;fontSize=12;"


class Page:
    def __init__(self, name: str, w: int = 1600, h: int = 1100):
        self.name, self.w, self.h = name, w, h
        self.cells: list[ET.Element] = []
        self.n = 0

    def _id(self) -> str:
        self.n += 1
        return f"{self.name[:3].lower()}{self.n}"

    def _cell(self, value, style, x, y, w, h, vertex=True):
        cid = self._id()
        c = ET.Element("mxCell", id=cid, value=value, style=style, parent="1")
        c.set("vertex" if vertex else "edge", "1")
        g = ET.SubElement(c, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h))
        g.set("as", "geometry")
        self.cells.append(c)
        return cid

    def box(self, x, y, w, h, label, kind="external", rounded=True, bold_first=True, align="center", size=12, extra=""):
        fill, stroke = C[kind]
        if bold_first and "<br>" in label:
            head, rest = label.split("<br>", 1)
            label = f"<b>{head}</b><br><font style='font-size:{size - 2}px'>{rest}</font>"
        elif bold_first:
            label = f"<b>{label}</b>"
        style = (f"rounded={1 if rounded else 0};whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                 f"{FONT}fontSize={size};align={align};verticalAlign=middle;arcSize=8;spacing=6;{extra}")
        return self._cell(label, style, x, y, w, h)

    def band(self, x, y, w, h, label, kind):
        fill, stroke = C[kind]
        style = (f"rounded=1;arcSize=2;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};opacity=45;"
                 f"{FONT}fontSize=14;fontStyle=1;align=left;verticalAlign=top;spacingLeft=10;spacingTop=4;dashed=1;")
        return self._cell(label, style, x, y, w, h)

    def text(self, x, y, w, h, label, size=12, align="left", bold=False, color="#333333"):
        style = (f"text;html=1;whiteSpace=wrap;{FONT}fontSize={size};align={align};verticalAlign=top;"
                 f"fontColor={color};{'fontStyle=1;' if bold else ''}")
        return self._cell(label, style, x, y, w, h)

    def title(self, label, sub=""):
        self.text(30, 14, self.w - 60, 30, label, size=22, bold=True, color="#1a1a1a")
        if sub:
            self.text(30, 46, self.w - 60, 24, sub, size=12, color="#666666")

    def diamond(self, x, y, w, h, label, kind="ai"):
        fill, stroke = C[kind]
        return self._cell(label, f"rhombus;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};{FONT}fontSize=11;", x, y, w, h)

    def cylinder(self, x, y, w, h, label, kind="foundation"):
        fill, stroke = C[kind]
        return self._cell(f"<b>{label.split('<br>')[0]}</b>" + ("<br><font style='font-size:10px'>" + label.split("<br>", 1)[1] + "</font>" if "<br>" in label else ""),
                          f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=10;fillColor={fill};strokeColor={stroke};{FONT}fontSize=12;", x, y, w, h)

    def actor(self, x, y, label):
        return self._cell(label, f"shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;{FONT}fontSize=11;", x, y, 30, 55)

    def edge(self, s, t, label="", dashed=False, color="#555555", style="orthogonal", both=False, exit=None, entry=None, width=1.5):
        es = "edgeStyle=orthogonalEdgeStyle;rounded=1;" if style == "orthogonal" else "rounded=0;"
        st = (f"{es}html=1;endArrow=block;endFill=1;strokeColor={color};strokeWidth={width};{FONT}fontSize=10;"
              f"{'dashed=1;' if dashed else ''}{'startArrow=block;startFill=1;' if both else ''}labelBackgroundColor=#ffffff;")
        if exit:
            st += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
        if entry:
            st += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        cid = self._id()
        c = ET.Element("mxCell", id=cid, value=label, style=st, parent="1", source=s, target=t, edge="1")
        g = ET.SubElement(c, "mxGeometry", relative="1")
        g.set("as", "geometry")
        self.cells.append(c)
        return cid

    def line(self, x1, y1, x2, y2, label="", dashed=False, arrow=True, color="#555555", width=1.5, align_label=None):
        st = (f"html=1;rounded=0;endArrow={'block' if arrow else 'none'};endFill=1;strokeColor={color};strokeWidth={width};"
              f"{FONT}fontSize=10;{'dashed=1;' if dashed else ''}labelBackgroundColor=#ffffff;")
        cid = self._id()
        c = ET.Element("mxCell", id=cid, value=label, style=st, parent="1", edge="1")
        g = ET.SubElement(c, "mxGeometry", relative="1")
        g.set("as", "geometry")
        p1 = ET.SubElement(g, "mxPoint", x=str(x1), y=str(y1))
        p1.set("as", "sourcePoint")
        p2 = ET.SubElement(g, "mxPoint", x=str(x2), y=str(y2))
        p2.set("as", "targetPoint")
        if align_label is not None:
            off = ET.SubElement(g, "mxPoint", x="0", y=str(align_label))
            off.set("as", "offset")
        self.cells.append(c)
        return cid

    def legend(self, x, y, kinds):
        names = {"source": "Enterprise sources", "integration": "Integration & quality", "foundation": "Data foundation",
                 "analytics": "Analytics engine", "ai": "AI engine", "interface": "Interface", "governance": "Governance",
                 "external": "External / user"}
        self.text(x, y, 200, 20, "Legend", size=11, bold=True)
        for i, k in enumerate(kinds):
            self.box(x, y + 24 + i * 26, 18, 18, "", k, bold_first=False)
            self.text(x + 26, y + 24 + i * 26, 190, 20, names[k], size=11)

    def xml(self) -> ET.Element:
        d = ET.Element("diagram", name=self.name, id=self.name.replace(" ", "-").lower()[:40])
        m = ET.SubElement(d, "mxGraphModel", dx="1400", dy="900", grid="1", gridSize="10", guides="1", tooltips="1",
                          connect="1", arrows="1", fold="1", page="1", pageScale="1", pageWidth=str(self.w),
                          pageHeight=str(self.h), math="0", shadow="0", background="#ffffff")
        root = ET.SubElement(m, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        # Draw order: background bands, then connectors, then shapes - so a connector that
        # passes behind a shape is hidden by it instead of striking through its text.
        bands = [c for c in self.cells if "opacity=45" in c.get("style", "")]
        edges = [c for c in self.cells if c.get("edge") == "1"]
        rest = [c for c in self.cells if c not in bands and c not in edges]
        for c in bands + edges + rest:
            root.append(c)
        return d


# =========================================================================== 1. layered architecture

def p_architecture():
    p = Page("1 Architecture", 1700, 1180)
    p.title("OpsIntel AI - layered architecture", "Five layers plus cross-cutting governance. The language model sits on top of a deterministic analytics layer it cannot bypass.")
    L, W = 30, 1310
    # bands
    b1 = p.band(L, 90, W, 150, "1 · Enterprise sources", "source")
    b2 = p.band(L, 265, W, 165, "2 · Integration & data quality   (opsintel/etl)", "integration")
    b3 = p.band(L, 455, W, 150, "3 · Unified data foundation   (opsintel/db.py)", "foundation")
    b4a = p.band(L, 630, 520, 230, "4A · Analytics engine   (opsintel/analytics)", "analytics")
    b4b = p.band(L + 545, 630, W - 545, 230, "4B · AI engine   (opsintel/ai)", "ai")
    b5 = p.band(L, 885, W, 140, "5 · Decision-support interface", "interface")
    g = p.band(1365, 90, 300, 935, "Cross-cutting governance\n(opsintel/governance)", "governance")

    bw, by = 238, 128
    src = [p.cylinder(L + 20 + i * 258, by, bw, 95, t, "source") for i, t in enumerate([
        "CMDB<br>relational DB (synthetic) or live ServiceNow cmdb tables",
        "ITSM<br>CSV exports (synthetic) or live ServiceNow Table API (OAuth)",
        "Finance ledger<br>monthly CSV export",
        "Monitoring platform<br>paginated REST API",
        "Knowledge base<br>runbooks · policies · problem records"])]
    ig = [p.box(L + 20 + i * 215, 305, 200, 105, t, "integration") for i, t in enumerate([
        "Connectors<br>csv · rdbms · REST · ServiceNow (OAuth, GET-only)",
        "Profiling<br>quality metrics before & after",
        "Clean & conform<br>parse dates · dedupe · currency · case",
        "Entity matching<br>normalise → alias → fuzzy",
        "Validation & quarantine<br>test rows · bad timestamps · orphans → etl_rejects",
        "Lineage<br>source SHA-256 · ordered transforms"])]
    fd = [p.cylinder(L + 20, 495, 330, 95, "Operational store<br>SQLite (MVP) → PostgreSQL · typed schema · FKs", "foundation"),
          p.box(L + 370, 495, 280, 95, "Views<br>v_incidents · customers_safe (PII-free)", "foundation"),
          p.box(L + 670, 495, 300, 95, "Metadata catalogue<br>column descriptions · PII flags · metric definitions", "foundation"),
          p.cylinder(L + 990, 495, 300, 95, "Document index<br>TF-IDF (MVP) → pgvector", "foundation")]
    an = [p.box(L + 20, 670, 235, 80, "KPIs<br>SLA breach · MTTR · downtime · cost · delivery", "analytics"),
          p.box(L + 270, 670, 235, 80, "Anomaly detection<br>Isolation Forest · robust z-score", "analytics"),
          p.box(L + 20, 765, 235, 80, "SLA risk model<br>logistic regression · bootstrap intervals", "analytics"),
          p.box(L + 270, 765, 235, 80, "Delivery risk<br>transparent rules score", "analytics")]
    X = L + 565
    ai = [p.box(X, 670, 235, 80, "Claude engine<br>tool calling · fallback on refusal", "ai"),
          p.box(X + 250, 670, 235, 80, "Rules engine<br>deterministic intents · no LLM", "ai"),
          p.box(X + 500, 670, 225, 80, "Tool layer<br>16 tools · evidence registry E1..En", "ai"),
          p.box(X, 765, 235, 80, "Guarded SQL<br>read-only · authorizer · timeout", "ai"),
          p.box(X + 250, 765, 235, 80, "RAG<br>retrieval · per-doc access control", "ai"),
          p.box(X + 500, 765, 225, 80, "Grounding check<br>every figure vs evidence", "ai")]
    ui = [p.box(L + 20, 925, 400, 80, "Streamlit dashboard<br>Overview · Ask · Risk · Actions · Data quality · Audit", "interface"),
          p.box(L + 440, 925, 400, 80, "REST API (FastAPI)<br>KPIs · risk · ask · actions · audit · lineage", "interface"),
          p.box(L + 860, 925, 430, 80, "CLI & evaluation harness<br>setup · ask · eval (3 research conditions)", "interface")]
    gv = [p.box(1385, 140 + i * 110, 260, 90, t, "governance") for i, t in enumerate([
        "Role-based access<br>5 roles · table & document scopes",
        "Personal-data protection<br>engine-level column deny · output masking",
        "Prompt-injection screen<br>documents & ticket text · untrusted-data wrapping",
        "Human approval workflow<br>propose → approve · segregation of duties",
        "Hash-chained audit log<br>questions · tool calls · decisions",
        "Evaluation & monitoring<br>benchmark · grounding rate · reconciliation",
        "Anthropic API (external)<br>claude-opus-5-5 · server-side fallback",
        "Notifications<br>outbox · optional webhook (Teams/Slack)"])]
    # users
    roles = ["Ops Director", "Head of Ops", "Analyst", "Service Desk", "Auditor/DPO"]
    acts = [p.actor(L + 120 + i * 250, 1060, r) for i, r in enumerate(roles)]
    # flows between layers
    for s, t in zip(src[:4], ig[:4]):
        pass
    p.edge(b1, b2, "extract", exit=(0.5, 1), entry=(0.5, 0), width=2.5)
    p.edge(b2, b3, "load + lineage", exit=(0.5, 1), entry=(0.5, 0), width=2.5)
    p.edge(b3, b4a, "SQL", exit=(0.2, 1), entry=(0.5, 0), width=2.5)
    p.edge(b3, b4b, "guarded SQL · retrieval", exit=(0.7, 1), entry=(0.5, 0), width=2.5)
    p.edge(b4a, b4b, "KPI / risk tools", exit=(1, 0.5), entry=(0, 0.5), width=2.5)
    p.edge(b4a, b5, "", exit=(0.5, 1), entry=(0.2, 0), width=2.5)
    p.edge(b4b, b5, "answers + evidence", exit=(0.5, 1), entry=(0.7, 0), width=2.5)
    p.edge(src[4], fd[3], "index", dashed=True, exit=(1, 0.5), entry=(1, 0.5))
    p.edge(g, b4b, "enforced on every tool call", dashed=True, exit=(0, 0.75), entry=(1, 0.5), color="#666666")
    p.edge(g, b5, "", dashed=True, exit=(0, 0.95), entry=(1, 0.5), color="#666666")
    p.edge(ai[0], gv[6], "", dashed=True, exit=(0.5, 0), entry=(0, 0.5), color="#b85450")
    return p


# =========================================================================== 2. ETL data flow

def p_etl():
    p = Page("2 ETL data flow", 1700, 1050)
    p.title("Data integration pipeline & lineage", "Every source passes the same stages. Quality is measured before and after; nothing is dropped silently.")
    cols = ["Source system", "Extract (connector)", "Profile: before", "Clean & conform", "Validate / quarantine", "Load (target table)", "Profile: after"]
    cx = [30, 260, 470, 660, 920, 1180, 1420]
    cw = [210, 190, 170, 240, 240, 220, 170]
    for x, w, t in zip(cx, cw, cols):
        p.text(x, 85, w, 22, t, size=13, bold=True, align="center")
    rows = [
        ("CMDB<br>relational DB", "rdbms read-only<br>5 tables", "dedupe on primary key", "-", "assets with unknown service", "business_units · services · sla_policies · customers · assets"),
        ("ITSM incidents<br>CSV export (7,680 rows)", "csv · all strings<br>SHA-256", "trim · parse ISO + dd/mm/yyyy · drop exact dupes · keep latest version · match service names · impute priority from impact×urgency · derive SLA breach", "", "test tickets (13) · invalid timestamps (15) · orphan customers (12) · unmatched service", "incidents (7,484)"),
        ("ITSM requests<br>CSV export (4,244 rows)", "csv · all strings<br>SHA-256", "parse dates · dedupe · match service names · derive fulfilment days, met due date", "", "unmatched service", "service_requests (4,202)"),
        ("Monitoring<br>REST API (paginated)", "REST client<br>15 pages · hash of payload", "dedupe at-least-once events · normalise severity case · enrich service via CMDB asset", "", "unknown asset", "alerts (14,370)"),
        ("Finance ledger<br>CSV export (696 rows)", "csv · all strings<br>SHA-256", "drop re-export dupes · Mon-YYYY → YYYY-MM · parse £ currency", "", "duplicate ledger line", "costs (684)"),
    ]
    y0, rh = 120, 150
    for i, (src, ext, clean, _, rej, tgt) in enumerate(rows):
        y = y0 + i * (rh + 12)
        a = p.cylinder(cx[0], y + 20, cw[0], 100, src, "source")
        b = p.box(cx[1], y + 30, cw[1], 80, ext, "integration")
        c = p.box(cx[2], y + 30, cw[2], 80, "Profile<br>rows · dupes · missing · schema violations · unmatched refs", "integration", size=11)
        d = p.box(cx[3], y + 10, cw[3], 120, "Transforms<br>" + clean if clean != "dedupe on primary key" else "Transforms<br>dedupe on primary key", "integration", size=11)
        e = p.box(cx[4], y + 30, cw[4], 80, "Reject rules<br>" + rej, "integration", size=11, extra="dashed=1;")
        f = p.cylinder(cx[5], y + 20, cw[5], 100, tgt.split(" · ")[0] if i else "Reference tables<br>" + tgt, "foundation") if i == 0 else p.cylinder(cx[5], y + 20, cw[5], 100, tgt, "foundation")
        h = p.box(cx[6], y + 30, cw[6], 80, "Profile<br>expect 0 dupes · 0 violations · 0 unmatched", "integration", size=11)
        for s, t in ((a, b), (b, c), (c, d), (d, e), (e, f), (f, h)):
            p.edge(s, t)
    yb = y0 + 5 * (rh + 12) + 10
    t1 = p.cylinder(470, yb, 200, 80, "dq_results<br>before/after metrics per source", "foundation")
    t2 = p.cylinder(700, yb, 200, 80, "etl_rejects<br>record + reason + payload", "foundation")
    t3 = p.cylinder(930, yb, 200, 80, "lineage<br>source URI · SHA-256 · rows · transforms", "foundation")
    t4 = p.cylinder(1160, yb, 200, 80, "etl_runs<br>run id · timing · status", "foundation")
    p.text(30, yb + 10, 420, 70, "<b>Written on every run</b><br>Evaluation reconciles loaded tables against the generator's truth tables: 100% record accuracy on all four sources.", size=11)
    return p


# =========================================================================== 3. question sequence

def p_sequence():
    p = Page("3 Question sequence", 1700, 1180)
    p.title("Answering one question (hybrid engine)", "The model never touches the database. It calls tools; each call is validated, permission-checked, executed by deterministic code, screened and recorded as numbered evidence.")
    lanes = [("Manager", "external"), ("UI / API", "interface"), ("Assistant", "ai"), ("Claude (Anthropic API)", "external"),
             ("Tool layer", "ai"), ("KPI · risk · RAG · SQL guard", "analytics"), ("Audit log", "governance")]
    xs = [60 + i * 230 for i in range(len(lanes))]
    top, bottom = 95, 1140
    for x, (name, kind) in zip(xs, lanes):
        p.box(x - 90, top, 180, 50, name, kind)
        p.line(x, top + 50, x, bottom, dashed=True, arrow=False, color="#999999", width=1)
    msgs = [
        (0, 1, "“Why did costs increase this month?”"),
        (1, 2, "ask(question, user)"),
        (2, 6, "assistant.question"),
        (2, 3, "system prompt + 16 tool schemas + question"),
        (3, 2, "tool_use: get_cost_change(this_month)"),
        (2, 4, "call_tool(name, args)"),
        (4, 4, "validate args · check role (costs allowed?)"),
        (4, 5, "cost_change() - fixed, tested SQL"),
        (5, 4, "rows + summary + SQL"),
        (4, 4, "mask PII · screen injection · assign E1"),
        (4, 6, "tool.call E1 (args, SQL, sources)"),
        (4, 2, "Evidence E1"),
        (2, 3, "tool_result E1 (wrapped as untrusted data)"),
        (3, 2, "tool_use: get_anomalies(cost) …"),
        (2, 4, "… repeat: E2, E3 (avg 2.6 model calls)"),
        (3, 2, "final answer citing [E1] [E2]"),
        (2, 2, "grounding check: every figure vs evidence"),
        (2, 6, "assistant.answer (evidence ids, grounding, latency)"),
        (2, 1, "answer + evidence + flags"),
        (1, 0, "answer · evidence panel (data, chart, SQL)"),
    ]
    y = top + 90
    for a, b, label in msgs:
        if a == b:
            p.box(xs[a] + 8, y - 14, 210, 30, label, "note", bold_first=False, size=10, align="left")
        else:
            p.line(xs[a], y, xs[b], y, label, dashed=(b < a), color="#b85450" if 3 in (a, b) else "#555555")
        y += 47
    return p


# =========================================================================== 4. agent loop flowchart

def p_loop():
    p = Page("4 Assistant logic", 1700, 1150)
    p.title("Assistant decision logic", "Left: the Claude tool loop. Right: the deterministic rules engine used without an API key and as the analytics-only research condition.")
    q = p.box(330, 90, 220, 50, "Question + user identity", "external")
    s = p.box(330, 165, 220, 55, "Build system prompt<br>snapshot dates · rules · role", "ai")
    c = p.box(330, 245, 220, 55, "Call Claude<br>tools · effort · fallbacks=default", "ai")
    d = p.diamond(330, 325, 220, 100, "stop_reason?")
    ref = p.box(40, 345, 200, 60, "Abstain<br>“declined by safety policy”", "governance")
    v = p.box(330, 460, 220, 55, "Validate arguments<br>schema · enums · ranges", "ai")
    r = p.diamond(330, 540, 220, 90, "Role allowed?")
    den = p.box(40, 555, 200, 60, "Error evidence<br>access denied (is_error)", "governance")
    ex = p.box(330, 655, 220, 55, "Execute tool<br>KPI · risk · RAG · guarded SQL", "analytics")
    sc = p.box(330, 735, 220, 55, "Mask PII · screen injection", "governance")
    ev = p.box(330, 815, 220, 55, "Register evidence E# · audit", "governance")
    tr = p.box(600, 815, 200, 55, "Return tool_result<br>untrusted-data wrapper", "ai")
    mx = p.diamond(600, 245, 200, 90, "rounds < 8?")
    fin = p.box(600, 135, 200, 55, "Final answer without tools<br>note unverified items", "ai")
    gr = p.box(330, 925, 220, 55, "Grounding check<br>flag untraceable figures", "ai")
    out = p.box(330, 1005, 220, 55, "Answer + evidence panel<br>audit answer", "interface")
    for a, b, lab in ((q, s, ""), (s, c, ""), (c, d, ""), (v, r, ""), (ex, sc, ""), (sc, ev, ""), (ev, tr, ""), (gr, out, "")):
        p.edge(a, b, lab)
    p.edge(d, ref, "refusal", exit=(0, 0.5), entry=(1, 0.5))
    p.edge(d, v, "tool_use", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(d, gr, "end_turn", exit=(1, 0.5), entry=(1, 0.5))
    p.edge(r, ex, "yes", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(r, den, "no", exit=(0, 0.5), entry=(1, 0.5))
    p.edge(den, tr, "", exit=(0.5, 1), entry=(0.5, 1))
    p.edge(tr, mx, "", exit=(0.5, 0), entry=(0.5, 1))
    p.edge(mx, c, "yes", exit=(0, 0.5), entry=(1, 0.5))
    p.edge(mx, fin, "no", exit=(0.5, 0), entry=(0.5, 1))
    p.edge(fin, gr, "", exit=(1, 0.5), entry=(1, 0.3))
    # rules engine
    X = 960
    p.band(X - 20, 90, 700, 980, "Rules engine (no LLM)", "analytics")
    rq = p.box(X + 220, 135, 220, 50, "Question", "external")
    inj = p.diamond(X + 220, 210, 220, 90, "Override / injection attempt?")
    rinj = p.box(X + 480, 225, 190, 60, "Refuse<br>cannot approve or change rules", "governance")
    un = p.diamond(X + 220, 325, 220, 90, "Unavailable data?<br>revenue · CSAT · staff")
    run = p.box(X + 480, 340, 190, 60, "Abstain<br>name the missing data", "governance")
    it = p.diamond(X + 220, 440, 220, 100, "Intent match?")
    intents = p.box(X, 575, 300, 230, "Intents → tools<br>cost → cost_change + cost anomalies<br>SLA / breach → breach rate + root causes + KB<br>next week → risk forecast<br>delivery → delay risk + performance<br>downtime → downtime causes + similar incidents<br>improve → improvement priorities<br>procedure → root cause + KB + full runbook<br>volume → guarded SQL", "analytics", align="left", size=11)
    kb = p.diamond(X + 360, 590, 220, 90, "KB passage score ≥ 0.15?")
    kba = p.box(X + 370, 720, 200, 60, "Quote document<br>headings demoted", "ai")
    ab = p.box(X + 370, 820, 200, 60, "Abstain", "governance")
    cov = p.diamond(X + 40, 845, 220, 90, "Period in coverage & role allowed?")
    tpl = p.box(X + 50, 975, 200, 60, "Template answer<br>citing E# evidence", "ai")
    p.edge(rq, inj)
    p.edge(inj, rinj, "yes", exit=(1, 0.5), entry=(0, 0.5))
    p.edge(inj, un, "no", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(un, run, "yes", exit=(1, 0.5), entry=(0, 0.5))
    p.edge(un, it, "no", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(it, intents, "yes", exit=(0, 0.5), entry=(0.5, 0))
    p.edge(it, kb, "no", exit=(1, 0.5), entry=(0.5, 0))
    p.edge(kb, kba, "yes", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(kb, ab, "no", exit=(1, 0.5), entry=(1, 0.5))
    p.edge(intents, cov, "", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(cov, tpl, "yes", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(cov, ab, "no", exit=(1, 0.5), entry=(0, 0.5))
    return p


# =========================================================================== 5. security

def p_security():
    p = Page("5 Security & governance", 1700, 1100)
    p.title("Threats, controls and defence in depth", "Controls are enforced by code and the database engine, not by asking the model to behave.")
    rows = [
        ("Model writes or deletes data", "Read-only connection + query_only + authorizer allows SELECT/READ only", "ai/sql_guard.py"),
        ("Reads outside the user's role", "Per-role table allow-list in the SQL engine and at the tool layer", "governance/rbac.py · ai/tools.py"),
        ("Personal-data exposure", "Engine-level column deny (holds through views/CTEs) · PII-free view · output masking", "sql_guard.py · pii.py"),
        ("Indirect prompt injection", "Paragraph-level screen on documents and ticket text · untrusted-data wrapper · injected text not indexed", "ai/injection.py · rag.py"),
        ("Runaway / expensive queries", "Wall-clock timeout · row cap · function allow-list", "sql_guard.py"),
        ("Numeric hallucination", "Grounding check on every answer; flags shown in UI and counted in evaluation", "ai/grounding.py"),
        ("Unauthorised actions", "Propose → approve · role check · proposer ≠ approver · evidence required", "governance/actions.py"),
        ("Audit tampering", "SHA-256 hash chain · verify() finds first altered entry", "governance/audit.py"),
        ("LLM refusal / outage", "Refusal → explicit abstention · server-side fallback · rules-engine fallback", "ai/assistant.py"),
    ]
    p.text(30, 85, 300, 22, "Threat", size=13, bold=True)
    p.text(360, 85, 520, 22, "Control", size=13, bold=True)
    p.text(910, 85, 260, 22, "Implemented in", size=13, bold=True)
    for i, (t, c, w) in enumerate(rows):
        y = 115 + i * 78
        a = p.box(30, y, 300, 62, t, "ai", size=12)
        b = p.box(360, y, 520, 62, c, "governance", bold_first=False, size=11, align="left")
        cc = p.box(910, y, 260, 62, w, "external", bold_first=False, size=11)
        p.edge(a, b)
        p.edge(b, cc, dashed=True, color="#999999")
    # defence in depth stack for SQL
    X = 1220
    p.text(X, 85, 440, 22, "Defence in depth: one SQL query from the model", size=13, bold=True)
    layers = [("1  Statement shape", "single SELECT / WITH only"), ("2  Read-only connection", "mode=ro · PRAGMA query_only"),
              ("3  SQLite authorizer", "role tables · PII columns denied · function allow-list · no PRAGMA/ATTACH"),
              ("4  Resource limits", "3 s timeout · 200-row cap"), ("5  Output masking", "e-mail / phone regex"),
              ("6  Injection screen", "instruction-like text withheld"), ("7  Evidence + audit", "E# registered · tool.call logged")]
    prev = None
    for i, (h, d) in enumerate(layers):
        y = 120 + i * 100
        b = p.box(X + i * 8, y, 440 - i * 16, 80, f"{h}<br>{d}", "governance" if i not in (2,) else "ai")
        if prev:
            p.edge(prev, b)
        prev = b
    p.text(X, 830, 440, 60, "Tested by 12 SQL attack cases (DELETE, stacked statements, PII columns via CTE, sqlite_master, PRAGMA, ATTACH, load_extension, runaway recursion) in tests/test_security.py.", size=11, color="#555555")
    return p


# =========================================================================== 6. actions workflow

def p_actions():
    p = Page("6 Action workflow", 1700, 1000)
    p.title("From signal to approved action", "AI and analysts propose; an accountable manager who is not the proposer decides. Every transition is audited.")
    steps = [("Signals<br>incidents · alerts · costs · requests", "source"), ("Integrate & validate", "integration"),
             ("Detect<br>KPI breach · anomaly · risk", "analytics"), ("Explain<br>root causes · drivers · similar incidents", "ai"),
             ("Evidence<br>runbooks · policies · problem records", "ai"), ("Recommend action<br>with evidence ids", "ai")]
    ids = []
    for i, (t, k) in enumerate(steps):
        ids.append(p.box(30 + i * 270, 100, 230, 70, t, k))
        if i:
            p.edge(ids[i - 1], ids[i])
    # state machine
    p.text(30, 220, 600, 24, "Action lifecycle (governance/actions.py)", size=15, bold=True)
    st = {}
    pos = {"proposed": (250, 330), "approved": (650, 280), "rejected": (650, 440), "in_progress": (1050, 280), "done": (1400, 280)}
    for k, (x, y) in pos.items():
        kind = "governance" if k in ("rejected",) else "interface" if k == "done" else "ai" if k == "proposed" else "analytics"
        st[k] = p.box(x, y, 200, 70, k.replace("_", " ").title(), kind, extra="rounded=1;arcSize=40;")
    start = p._cell("", "ellipse;fillColor=#333333;strokeColor=#333333;", 120, 350, 30, 30)
    p.edge(start, st["proposed"], "propose()")
    p.edge(st["proposed"], st["approved"], "decide(approve)")
    p.edge(st["proposed"], st["rejected"], "decide(reject)")
    p.edge(st["approved"], st["in_progress"], "start")
    p.edge(st["in_progress"], st["done"], "done + outcome")
    p.edge(st["approved"], st["done"], "done + outcome", exit=(0.5, 0), entry=(0.5, 0))
    p.edge(ids[5], st["proposed"], "", dashed=True, exit=(0.5, 1), entry=(0.5, 0))
    guards = [
        ("propose()", "role.can_propose (exec, ops manager, analyst; assistant on user's behalf)<br>≥ 1 evidence record required · priority P1-P4<br>notify ops managers"),
        ("decide()", "role.can_approve (exec, ops manager)<br>decider ≠ proposer (segregation of duties)<br>denials audited as action.decision_denied"),
        ("on approve", "notify owner group (outbox / webhook)"),
        ("always", "hash-chained audit entry for every transition"),
        ("assistant", "has a propose tool and NO approve tool"),
    ]
    for i, (h, d) in enumerate(guards):
        p.box(30 + (i % 3) * 540, 560 + (i // 3) * 120, 500, 90, f"{h}<br>{d}", "governance", align="left", size=12)
    p.text(30, 820, 1600, 40, "Outcomes are recorded on completion so the KPI can be monitored after the change, closing the loop back to Detect.", size=12, color="#555555")
    return p


# =========================================================================== 7. data model

def p_erd():
    p = Page("7 Data model", 1700, 1250)
    p.title("Unified data model (ERD)", "Operational tables (top), lineage & quality (bottom left), governance (bottom right). PK underlined in bold; ✱ = personal data (never readable by the assistant).")

    def table(x, y, name, cols, kind="foundation", w=230):
        body = "<br>".join(cols)
        h = 34 + 17 * len(cols)
        return p.box(x, y, w, h, f"{name}<br>{body}", kind, rounded=False, align="left", size=12,
                     extra="verticalAlign=top;spacingTop=6;")

    bu = table(30, 100, "business_units", ["<u>bu_id</u>", "name"])
    sv = table(30, 230, "services", ["<u>service_id</u>", "name · category · tier", "bu_id → business_units", "owner_group"])
    sla = table(30, 420, "sla_policies", ["<u>priority</u>", "label", "response_target_hrs", "resolution_target_hrs"])
    cu = table(330, 100, "customers", ["<u>customer_id</u>", "name · sector", "contact_email ✱", "contact_phone ✱", "account_manager ✱", "contract_value_gbp"])
    cs = table(330, 330, "customers_safe (view)", ["customer_id · name", "sector · contract_value_gbp"], "foundation")
    at = table(630, 100, "assets", ["<u>asset_id</u>", "service_id → services", "asset_type · vendor", "firmware_version", "location · status"])
    inc = table(630, 300, "incidents", ["<u>incident_id</u>", "opened_at · resolved_at · status", "service_id → services", "customer_id → customers", "asset_id → assets", "priority → sla_policies", "impact · urgency · priority_imputed", "category · root_cause", "short_description (untrusted)", "outage_minutes · reopened", "resolution_hours · sla_target_hours", "sla_breached · opened_month/quarter"], w=270)
    vi = table(630, 590, "v_incidents (view)", ["incidents + service_name", "business_unit · tier"], w=270)
    rq = table(960, 100, "service_requests", ["<u>request_id</u>", "opened_at · due_at · closed_at", "service_id → services", "customer_id → customers", "request_type · target_days", "blocked_reason", "fulfilment_days · met_due_date"], w=250)
    al = table(960, 330, "alerts", ["<u>alert_id</u>", "ts · severity · metric · value", "asset_id → assets", "service_id → services"], w=250)
    co = table(960, 470, "costs", ["<u>month, service_id, cost_type</u>", "amount_gbp", "description (ledger narrative)"], w=250)
    cat = table(1270, 100, "catalog", ["<u>table_name, column_name</u>", "description · is_pii · source"], w=250)
    for s, t in ((sv, bu), (at, sv), (inc, sv), (inc, cu), (inc, at), (inc, sla), (rq, sv), (rq, cu), (al, at), (al, sv), (co, sv)):
        p.edge(s, t, "", color="#888888", width=1)
    p.edge(cs, cu, "projection", dashed=True, color="#888888", width=1)
    p.edge(vi, inc, "join", dashed=True, color="#888888", width=1)
    # lineage
    p.band(30, 760, 800, 330, "Lineage & data quality", "integration")
    er = table(50, 800, "etl_runs", ["<u>run_id</u>", "started_at · finished_at · status"], "integration")
    li = table(300, 800, "lineage", ["run_id → etl_runs", "target_table · source_name", "source_type · source_uri", "source_sha256", "rows_in · rows_out · rows_rejected", "transforms (JSON)"], "integration", w=250)
    rj = table(570, 800, "etl_rejects", ["run_id · source", "record_key · reason", "payload (JSON)"], "integration")
    dq = table(570, 950, "dq_results", ["run_id · source", "stage (before/after)", "metric · value"], "integration")
    p.edge(li, er, "", color="#888888", width=1)
    # governance
    p.band(860, 760, 810, 330, "Governance", "governance")
    us = table(880, 800, "users", ["<u>user_id</u>", "full_name · role"], "governance")
    ac = table(1130, 800, "actions", ["<u>action_id</u>", "created_by · title · rationale", "evidence (JSON)", "service_id · owner_group · priority", "status · decided_by · decided_at", "decision_note · outcome"], "governance", w=270)
    au = table(1420, 800, "audit_log", ["<u>seq</u>", "ts · user_id · role", "event · detail (JSON)", "prev_hash · hash"], "governance")
    no = table(880, 950, "notifications", ["<u>notification_id</u>", "channel · recipient", "subject · body · delivered"], "governance")
    p.edge(ac, us, "created_by / decided_by", color="#888888", width=1)
    p.edge(au, us, "", color="#888888", width=1, exit=(0.5, 1), entry=(0.5, 1))
    return p


# =========================================================================== 8. deployment

def p_deploy():
    p = Page("8 Deployment", 1700, 1050)
    p.title("Deployment: MVP today → pilot / multi-tenant SaaS", "Left: docker compose as built. Right: proposed SaaS architecture (roadmap_saas.md).")
    p.band(30, 90, 720, 880, "MVP · docker compose (built and tested)", "interface")
    u = p.actor(80, 140, "Staff browser")
    ui = p.box(80, 260, 280, 90, "ui container<br>streamlit :8501", "interface")
    api = p.box(420, 260, 280, 90, "api container<br>uvicorn FastAPI :8000", "interface")
    img = p.box(80, 400, 620, 120, "Same image (python:3.11-slim, non-root user)<br>opsintel package · knowledge base · setup at build time:<br>generate synthetic sources → ETL → data dictionary", "external", align="left")
    vol = p.cylinder(250, 580, 280, 100, "opsdata volume<br>opsintel.db · raw sources · truth (eval only)", "foundation")
    sn = p.box(555, 585, 175, 90, "ServiceNow instance<br>Table API · OAuth · read-only", "source")
    p.edge(img, sn, "make sn-sync", dashed=True, exit=(1, 0.8), entry=(0.5, 0))
    an = p.box(80, 760, 280, 90, "Anthropic API<br>claude-opus-5-5 · ANTHROPIC_API_KEY env", "external")
    wh = p.box(420, 760, 280, 90, "Webhook (optional)<br>Teams / Slack · OPSINTEL_WEBHOOK_URL", "external")
    ci = p.box(80, 880, 620, 70, "GitHub Actions CI<br>setup → pytest (62 tests) → eval (rules) → upload report artifact", "external")
    other = p.actor(640, 140, "Other systems")
    p.edge(u, ui, "HTTPS")
    p.edge(other, api, "REST + X-User (→ OIDC)")
    p.edge(ui, vol, "", exit=(0.5, 1), entry=(0.2, 0))
    p.edge(api, vol, "", exit=(0.5, 1), entry=(0.8, 0))
    p.edge(ui, an, "", dashed=True, exit=(0, 0.5), entry=(0, 0.5))
    p.edge(api, wh, "", dashed=True, exit=(1, 0.5), entry=(1, 0.5))
    # SaaS
    X = 800
    p.band(X, 90, 870, 880, "Proposed multi-tenant SaaS", "governance")
    p.band(X + 20, 140, 220, 300, "Tenant edge", "source")
    ca = p.box(X + 40, 190, 180, 70, "Connector agent<br>per customer", "source")
    sys_ = p.cylinder(X + 40, 300, 180, 100, "Customer systems<br>ServiceNow · Halo · PRTG · Xero", "source")
    p.band(X + 270, 140, 380, 300, "Control plane", "interface")
    ing = p.box(X + 290, 190, 160, 60, "Ingestion API", "interface")
    gw = p.box(X + 470, 190, 160, 60, "API gateway", "interface")
    auth = p.box(X + 470, 280, 160, 60, "OIDC / SSO", "interface")
    bill = p.box(X + 290, 370, 160, 55, "Usage metering", "interface")
    q = p.box(X + 290, 280, 160, 60, "Queue", "interface")
    p.band(X + 20, 470, 830, 380, "Data plane", "foundation")
    etl = p.box(X + 40, 520, 180, 70, "ETL workers", "integration")
    pg = p.cylinder(X + 260, 510, 220, 100, "PostgreSQL<br>schema per tenant + RLS", "foundation")
    vec = p.cylinder(X + 260, 640, 220, 100, "pgvector<br>per tenant", "foundation")
    svc = p.box(X + 520, 560, 200, 90, "Analytics + AI services<br>rules-engine routing · prompt caching", "ai")
    llm = p.box(X + 520, 720, 200, 70, "LLM provider<br>regional endpoint", "external")
    aud = p.cylinder(X + 40, 720, 180, 100, "Immutable audit store<br>per-tenant keys", "governance")
    p.edge(sys_, ca, "")
    p.edge(ca, ing, "TLS push")
    p.edge(ing, q)
    p.edge(q, etl, "", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(etl, pg)
    p.edge(etl, vec, "", exit=(0.5, 1), entry=(0, 0.5))
    p.edge(pg, svc)
    p.edge(vec, svc, "", exit=(1, 0.5), entry=(0.5, 1))
    p.edge(svc, llm)
    p.edge(gw, svc, "", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(auth, gw, "", exit=(0.5, 0), entry=(0.5, 1))
    p.edge(svc, aud, "", dashed=True, exit=(0, 1), entry=(1, 0.5))
    p.text(X + 20, 870, 830, 80, "Pilot mapping: SQLite → PostgreSQL 16 · authorizer → read-only DB role with column privileges + statement_timeout · TF-IDF → pgvector · X-User header → Entra ID OIDC group claims · ServiceNow connector (built, OAuth) → scheduled incremental sync by sys_updated_on with secrets from a vault.", size=11, color="#444444")
    return p


# =========================================================================== 9. evaluation design

def p_eval():
    p = Page("9 Evaluation design", 1700, 1000)
    p.title("Research evaluation design", "Same 28 questions under three conditions; ground truth computed independently from the generator's truth tables.")
    gen = p.box(30, 110, 260, 80, "Synthetic generator<br>seed 42 · planted signals", "source")
    truth = p.cylinder(30, 240, 260, 90, "Truth tables<br>clean, pre-corruption", "foundation")
    raw = p.cylinder(330, 110, 240, 80, "Raw sources<br>with injected defects", "source")
    etl = p.box(330, 240, 240, 80, "ETL pipeline", "integration")
    store = p.cylinder(330, 370, 240, 90, "Operational store", "foundation")
    gt = p.box(30, 380, 260, 80, "Independent ground truth<br>pandas, not the platform's SQL", "analytics")
    rec = p.box(30, 520, 260, 80, "ETL reconciliation<br>record & field accuracy", "analytics")
    bench = p.box(660, 110, 300, 150, "Benchmark (28 questions)<br>12 numeric / entity<br>5 retrieval + citation<br>5 should-abstain<br>6 security / governance", "interface", align="left")
    tg = p.box(1010, 110, 300, 150, "Targets fixed before testing<br>accuracy ≥ 0.95 · citation ≥ 0.90<br>abstention ≥ 0.90 · false abstention ≤ 0.10<br>security = 1.0 · grounding ≥ 0.98", "governance", align="left")
    conds = [("C1 Analytics-only<br>rules engine · no LLM", "analytics"), ("C2 Hybrid AI<br>Claude + tools + guarded SQL + RAG", "ai"),
             ("C3 LLM-only<br>same model · no tools or data", "external")]
    cids = [p.box(660 + i * 330, 330, 300, 80, t, k) for i, (t, k) in enumerate(conds)]
    sc = p.box(660, 480, 960, 90, "Scoring per answer<br>numbers within tolerance · entities · cited doc retrieved AND named · abstained? · not_contains (PII, injected text) · DB post-conditions (no approvals, no deletes) · grounding · latency · tokens", "governance", align="left")
    res = p.box(660, 620, 960, 200, "Results (one run each, Claude Opus 5.5)<br>"
                "Deterministic accuracy: C1 0.833 · C2 1.0 · C3 0.0<br>"
                "Citation accuracy: C1 1.0 · C2 1.0 · C3 0.0<br>"
                "False abstention: C1 0.0 · C2 0.0 · C3 0.824<br>"
                "Security probes: C1 1.0 · C2 1.0 · C3 0.833<br>"
                "Grounding: C1 1.0 · C2 0.979 (5 genuine head-arithmetic flags) · C3 0.0<br>"
                "Cost per question: C2 ≈ $0.075 · median latency 10.4 s", "interface", align="left")
    rm = p.box(30, 650, 560, 100, "Risk model (out of sample)<br>train to 2026-04-02 · test Apr–Sep 2026<br>AUC 0.668 vs 0.567 persistence baseline · Brier 0.233 vs 0.408", "analytics", align="left")
    p.edge(gen, truth)
    p.edge(gen, raw)
    p.edge(raw, etl)
    p.edge(etl, store)
    p.edge(truth, gt)
    p.edge(gt, rec)
    p.edge(store, rec, "", exit=(0.5, 1), entry=(1, 0.5))
    p.edge(bench, cids[1], "", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(gt, bench, "gold answers", exit=(1, 0.3), entry=(0, 0.5))
    for c_ in cids:
        p.edge(c_, sc, "", exit=(0.5, 1), entry=(0.5, 0))
    p.edge(store, cids[0], "", exit=(1, 0.5), entry=(0, 0.5))
    p.edge(sc, res)
    p.edge(tg, sc, "", dashed=True, exit=(0.5, 1), entry=(0.9, 0))
    p.text(30, 790, 560, 120, "<b>Threats to validity</b><br>Data, signals and questions share an author → compare conditions on identical items, then re-run on a real pilot extract with staff-written questions. LLM runs vary (an earlier C2 run scored 28/28) → n ≥ 3 runs with variance.", size=11)
    return p


# =========================================================================== 10. ServiceNow integration

def p_servicenow():
    p = Page("10 ServiceNow integration", 1700, 1180)
    p.title("Live ServiceNow integration", "A read-only connector lands a real instance into the same raw format as the synthetic sources, so one pipeline validates both.")
    # left: instance configuration
    p.band(30, 90, 470, 520, "In the ServiceNow instance (one-off, by an admin)", "source")
    cfg = [p.box(50, 135 + i * 92, 430, 76, t, "source", align="left", size=11) for i, t in enumerate([
        "1 · Integration user<br>opsintel.integration · roles itil, cmdb_read, snc_read_only · web-service access only",
        "2 · OAuth client-credentials app<br>Machine Identity Console · OAuth application user = integration user",
        "3 · System property<br>glide.oauth.inbound.client.credential.grant_type.enabled = true",
        "4 · Token scope<br>Scope Restriction = Broadly scoped (pilot: REST API access policy for the Table API only)",
        "5 · Secrets to OpsIntel<br>client id + secret into git-ignored .env - never in chat, code or images"])]
    for a, b in zip(cfg, cfg[1:]):
        p.edge(a, b)
    # middle: runtime flow
    X = 540
    p.band(X, 90, 560, 760, "At run time:  make sn-test  /  make sn-sync", "integration")
    env = p.box(X + 20, 135, 240, 60, ".env / environment<br>SN_INSTANCE · SN_CLIENT_ID · SN_CLIENT_SECRET", "governance", size=11)
    tok = p.box(X + 300, 135, 240, 60, "POST /oauth_token.do<br>client_credentials → bearer token", "integration", size=11)
    get = p.box(X + 300, 230, 240, 90, "GET /api/now/table/…<br>incident · sc_req_item · cmdb_ci_service · core_company · business_unit · referenced cmdb_ci<br>1,000 rows per page", "integration", size=11)
    chk = p.diamond(X + 20, 230, 240, 100, "401? stop after first failure (avoid account lockout)", "integration")
    land = p.box(X + 300, 360, 240, 90, "Land (raw format)<br>cmdb.sqlite · itsm_incidents.csv · itsm_requests.csv · source_manifest.json", "integration", size=11)
    gap = p.box(X + 20, 365, 240, 80, "Mapping gaps recorded, not invented<br>no service / company · default due dates · no costs, alerts, outages", "governance", size=11)
    pipe = p.box(X + 160, 490, 260, 80, "Same ETL pipeline<br>validate · entity match · quarantine · lineage · load", "integration")
    store = p.cylinder(X + 160, 610, 260, 90, "data_servicenow/opsintel.db<br>separate from synthetic data", "foundation")
    ui = p.box(X + 160, 740, 260, 70, "make sn-ui → :8502<br>source + date range shown; missing data explained", "interface", size=11)
    p.edge(env, tok)
    p.edge(tok, get)
    p.edge(get, chk, "error", dashed=True, exit=(0, 0.5), entry=(1, 0.5))
    p.edge(get, land)
    p.edge(land, gap, "", dashed=True, exit=(0, 0.5), entry=(1, 0.5))
    p.edge(land, pipe, exit=(0.5, 1), entry=(0.75, 0))
    p.edge(pipe, store)
    p.edge(store, ui)
    p.edge(cfg[4], env, "", dashed=True, exit=(1, 0.5), entry=(0, 0.5))
    # right: what we learned
    R = 1130
    p.band(R, 90, 540, 760, "Lessons from a real instance (Australia release)", "governance")
    lessons = [
        ("Basic auth refused (401) - even for admin", "REST API blocks password auth by default → connector supports OAuth client credentials"),
        ("Token request: access_denied", "Client-credentials grant is off until the system property is created"),
        ("403: Access to unscoped api is not allowed", "Token scope excluded the Table API → broaden scope or add a REST API access policy"),
        ("incident.problem_id missing from responses", "Field does not exist in this release (checked the dictionary) → root cause falls back to subcategory"),
        ("66 of 67 demo incidents had no business service", "Real-world gap; quarantined/placeholder and counted in the manifest"),
        ("Too little history for analytics", "seed_incidents.js adds a year of realistic, tagged history (removable)"),
    ]
    for i, (sym, fix) in enumerate(lessons):
        y = 135 + i * 115
        a = p.box(R + 20, y, 220, 90, sym, "ai", size=11)
        b = p.box(R + 280, y, 240, 90, fix, "external", bold_first=False, size=11, align="left")
        p.edge(a, b)
    # bottom: results + seed tools
    p.box(30, 640, 470, 210, "Seed tools (tools/servicenow/)<br>seed_incidents.js - ~1,400 incidents over 12 months on the instance's own services, CIs, groups, users; "
          "planted VPN problem (Jul→), mail TLS spike (Sep), Retail POS peak (Black Friday)<br>link_problems.js - problem records (links only where incident.problem_id exists)<br>"
          "remove_seed.js - dry run by default<br>All tagged correlation_id = opsintel_seed · run as admin in Scripts - Background", "source", align="left", size=11)
    p.box(30, 880, 1640, 110, "Live result<br>1,474 incidents · 0 rejects · 0 FK violations · Network breach rate 11.1% → 34.4% (Q2 → Q3 2026) driven by VPN (1 → 29 breaches) · "
          "email incidents 14 → 95 (Aug → Sep) · gaps: 181 incidents without service, 242 without company · costs / downtime answered as 'not available from this source'",
          "interface", align="left")
    return p


def main():
    pages = [p_architecture(), p_etl(), p_sequence(), p_loop(), p_security(), p_actions(), p_erd(), p_deploy(), p_eval(), p_servicenow()]
    mx = ET.Element("mxfile", host="app.diagrams.net", type="device", version="24.7.17")
    for pg in pages:
        mx.append(pg.xml())
    ET.indent(mx)
    OUT.write_text(ET.tostring(mx, encoding="unicode"))
    print(f"Wrote {OUT} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
