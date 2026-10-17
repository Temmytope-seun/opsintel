"""Record a captioned demo walkthrough of both dashboards (Playwright video, uses installed Chrome).

    make ui && make sn-ui          # both dashboards running, ANTHROPIC_API_KEY in .env for the Claude engine
    .venv/bin/python -m playwright install ffmpeg   # once: Playwright's video encoder
    .venv/bin/python tools/record_demo.py

Writes docs/demo/opsintel_demo.webm. Follows docs/demo_script.md; asks Claude ~4 questions (~$0.30).
"""
from __future__ import annotations

import shutil
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "demo"
SYNTH, SN = "http://localhost:8501", "http://localhost:8502"
SIZE = {"width": 1280, "height": 800}

CSS = """
[data-testid=stSkillsNudge], [data-testid=stSkillsNudgeAnchor], [data-testid=stToast], [data-testid=stAppDeployButton],
[data-testid=stToolbar], [data-testid=stDecoration] { display: none !important; }
#demo-caption { position: fixed; left: 50%; top: 12px; pointer-events: none; transform: translateX(-50%); z-index: 2147483647;
  max-width: 1000px; padding: 12px 20px; border-radius: 10px; background: rgba(17, 24, 39, 0.92); color: #fff;
  font: 500 17px/1.45 -apple-system, "Segoe UI", sans-serif; box-shadow: 0 6px 24px rgba(0,0,0,.25); text-align: center; }
#demo-caption b { color: #93c5fd; }
"""


def prep(page: Page):
    page.add_style_tag(content=CSS)


def caption(page: Page, html: str, hold_ms: int = 3500):
    prep(page)
    page.evaluate("""(h) => { let d = document.getElementById('demo-caption');
        if (!d) { d = document.createElement('div'); d.id = 'demo-caption'; document.body.appendChild(d); }
        d.innerHTML = h; }""", html)
    page.wait_for_timeout(hold_ms)


def settle(page: Page, ms: int = 1500):
    page.wait_for_load_state("networkidle")
    page.wait_for_function("!document.querySelector('[data-testid=stStatusWidget]')", timeout=180_000)
    prep(page)
    page.wait_for_timeout(ms)


def view(page: Page, name: str):
    page.locator("[data-testid=stSidebar]").get_by_text(name, exact=True).click()
    settle(page)


def user(page: Page, label_part: str):
    page.locator("[data-testid=stSidebar] [data-testid=stSelectbox]").first.click()
    page.get_by_role("option").filter(has_text=label_part).first.click()
    settle(page)


def scroll(page: Page, px: int, steps: int = 6, pause: int = 450):
    for _ in range(steps):
        page.mouse.wheel(0, px // steps)
        page.wait_for_timeout(pause)


def ask(page: Page, question: str):
    count = "document.body.innerText.split('Engine:').length - 1"
    before = page.evaluate(count)
    box = page.get_by_placeholder("Ask a question about operations")
    box.click()
    box.type(question, delay=18)
    box.press("Enter")
    page.wait_for_function(f"{count} > {before}", timeout=240_000)
    settle(page, 1200)
    page.evaluate("document.querySelectorAll('[data-testid=stChatMessage]')[1]?.scrollIntoView({block:'start'})")
    page.wait_for_timeout(800)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport=SIZE, color_scheme="light", record_video_dir=str(OUT / "_raw"), record_video_size=SIZE)
        page = ctx.new_page()

        # 1. Overview
        page.goto(SYNTH)
        settle(page, 3000)
        caption(page, "<b>OpsIntel AI</b> - governed operational intelligence for IT service businesses.<br>"
                      "Four source systems unified: ITSM, CMDB, finance and monitoring (synthetic company).", 5000)
        caption(page, "Network SLA breaches jumped from 9% to 27% last quarter, and costs rose £58.6k this month. Why?", 4500)
        scroll(page, 600)
        caption(page, "Every chart comes from fixed, tested SQL - one definition per metric.", 3500)

        # 2. Ask: SLA breach (Claude)
        view(page, "Ask OpsIntel")
        caption(page, "Ask in plain English. The assistant can only call tools - it never touches the database directly.", 3500)
        ask(page, "Which service category had the highest SLA breach rate last quarter, and what explains the increase?")
        caption(page, "Each claim cites its evidence <b>[E1]</b>, <b>[E2]</b>… The cause comes from recorded root causes, "
                      "not from the model's imagination.", 5500)
        scroll(page, 1100, steps=10, pause=550)
        caption(page, "<b>All figures traced to evidence</b> - a grounding check compares every number with the tool results.", 4500)
        page.locator("[data-testid=stExpander]").first.click()
        settle(page, 800)
        scroll(page, 400)
        caption(page, "Open any evidence item to see the exact data and SQL behind it.", 4500)

        # 3. Role restriction
        user(page, "Service Desk")
        view(page, "Ask OpsIntel")
        caption(page, "Now signed in as a <b>service desk engineer</b>, who has no access to financial data.", 3500)
        ask(page, "Why did our operational costs increase this month?")
        caption(page, "The role restriction is enforced in the tool layer and the database engine - so the answer is a clear refusal.", 5000)

        # 4. Personal data + injection
        user(page, "Performance Analyst")
        view(page, "Ask OpsIntel")
        ask(page, "List the contact email addresses for all our customers.")
        caption(page, "Personal data is blocked by the database engine itself, not by asking the model nicely.", 5000)

        # 5. Risk
        view(page, "Risk & anomalies")
        caption(page, "Next week's SLA risk per service, with an uncertainty range and the main drivers.", 4000)
        scroll(page, 700)
        caption(page, "Out of sample it beats a naive baseline (AUC 0.67 vs 0.57) - presented as a prioritisation aid, not a forecast.", 5000)

        # 6. Actions + data quality + audit
        view(page, "Actions & approvals")
        caption(page, "Recommendations become <b>proposed actions</b>. A manager who is not the proposer must approve them.", 4500)
        view(page, "Data quality & lineage")
        caption(page, "Quality is measured before and after integration; bad records are quarantined with a reason; "
                      "every table has lineage back to its source.", 5500)
        user(page, "Internal Audit")
        view(page, "Audit log")
        caption(page, "Every question, tool call and decision is in a <b>hash-chained audit log</b> - tampering is detectable.", 5000)

        # 7. Live ServiceNow
        page.goto(SN)
        settle(page, 3000)
        caption(page, "The same platform on a <b>live ServiceNow instance</b>: OAuth, read-only integration user, same pipeline.", 5000)
        view(page, "Ask OpsIntel")
        ask(page, "What is driving the rise in Network incidents since July 2026?")
        caption(page, "It finds the VPN surge in the real instance's incident history - every figure traced to evidence.", 6000)
        scroll(page, 700, steps=8, pause=500)
        caption(page, "Evaluation: hybrid AI 28/28 correct; the same model without data 0/12 factual. "
                      "Full results in docs/technical_report.md.", 6000)

        video = page.video
        ctx.close()
        browser.close()
        target = OUT / "opsintel_demo.webm"
        shutil.move(video.path(), target)
        shutil.rmtree(OUT / "_raw", ignore_errors=True)
        print("saved", target, round(target.stat().st_size / 1e6, 1), "MB")


if __name__ == "__main__":
    main()
