"""Capture README screenshots of the running dashboards with Playwright (uses installed Chrome).

    make ui            # synthetic dashboard on :8501
    make sn-ui         # ServiceNow dashboard on :8502 (optional)
    .venv/bin/python tools/capture_screenshots.py

Writes docs/images/*.png. The 'Ask' screenshot calls the assistant once (Claude if a key is set).
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parent.parent / "docs" / "images"
SYNTH, SN = "http://localhost:8501", "http://localhost:8502"


HIDE_CHROME = """
[data-testid=stSkillsNudge], [data-testid=stSkillsNudgeAnchor], [data-testid=stToast], [data-testid=stAppDeployButton],
[data-testid=stToolbar], [data-testid=stDecoration] { display: none !important; }
"""


def settle(page: Page, ms: int = 2500):
    page.wait_for_load_state("networkidle")
    page.add_style_tag(content=HIDE_CHROME)
    page.wait_for_timeout(ms)
    page.wait_for_function("!document.querySelector('[data-testid=stStatusWidget]')", timeout=120_000)


def goto_view(page: Page, view: str):
    page.locator("[data-testid=stSidebar]").get_by_text(view, exact=True).click()
    settle(page)


def sign_in_as(page: Page, label_part: str):
    page.locator("[data-testid=stSidebar] [data-testid=stSelectbox]").first.click()
    page.get_by_role("option").filter(has_text=label_part).first.click()
    settle(page)


def shot(page: Page, name: str):
    OUT.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(OUT / f"{name}.png"))
    print("saved", name)


def capture(base: str, prefix: str, ask: str | None, views: list[str]):
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1, color_scheme="light")
        page.goto(base)
        settle(page, 4000)
        shot(page, f"{prefix}overview")
        if ask:
            goto_view(page, "Ask OpsIntel")
            page.get_by_text(ask, exact=True).click()
            page.wait_for_selector("text=Engine:", timeout=180_000)
            settle(page)
            page.set_viewport_size({"width": 1440, "height": 1400})
            page.wait_for_timeout(2000)  # let Streamlit finish its own auto-scroll first
            for _ in range(2):
                page.evaluate("document.querySelector('[data-testid=stChatMessage]').scrollIntoView({block: 'start'})")
                page.wait_for_timeout(700)
            shot(page, f"{prefix}ask")
            page.set_viewport_size({"width": 1440, "height": 1000})
        for v in views:
            if v == "Audit log":
                sign_in_as(page, "Internal Audit")
            goto_view(page, v)
            shot(page, prefix + v.lower().replace(" & ", "_").replace(" ", "_"))
        browser.close()


if __name__ == "__main__":
    targets = sys.argv[1:] or ["synthetic", "servicenow"]
    if "synthetic" in targets:
        capture(SYNTH, "", "Which service category had the highest SLA breach rate last quarter, and what explains the increase?",
                ["Risk & anomalies", "Actions & approvals", "Data quality & lineage", "Audit log"])
    if "servicenow" in targets:
        capture(SN, "servicenow_", None, [])
