from types import SimpleNamespace

import pytest

from opsintel.ai import grounding
from opsintel.ai.assistant import ABSTAIN_PREFIX, ClaudeEngine, RulesEngine, ask, extract_period

R = RulesEngine()


def test_rules_engine_answers_with_grounded_figures():
    a = ask("Which service category had the highest SLA breach rate last quarter, and what explains the increase?", "opsmgr.demo", engine=R)
    assert "Network" in a.answer and "Firmware" in a.answer and not a.abstained
    assert a.grounding["ungrounded"] == [] and a.grounding["figures"] >= 4
    assert {e.tool for e in a.evidence} >= {"get_sla_breach_rate", "get_root_causes"}


@pytest.mark.parametrize("q", ["What was our revenue in Q3?", "What was the SLA breach rate in Q2 2023?", "Tell me a joke"])
def test_rules_engine_abstains(q):
    a = ask(q, "analyst.demo", engine=R)
    assert a.abstained and a.answer.startswith(ABSTAIN_PREFIX)


def test_role_restriction_flows_through_assistant():
    a = ask("Why did costs increase this month?", "desk.demo", engine=R)
    assert a.abstained and "£" not in a.answer


def test_period_extraction():
    assert extract_period("breach rate in Q2 2026") == "2026Q2"
    assert extract_period("costs in August 2026") == "2026-08"
    assert extract_period("this month") == "this_month"
    assert extract_period("in 2023") == "2023Q4"


def test_grounding_flags_invented_numbers():
    g = grounding.check("Rate was 27.2% (+18.0 pp), cost £58.6k, made-up 31.5%. Step 3 on 2026-09-30, SVC-004.",
                        [{"a": 27.2, "b": 18.0, "c": 58568.0}])
    assert g["grounded"] == ["27.2%", "+18.0 pp", "£58.6k"] and g["ungrounded"] == ["31.5%"]


def test_grounding_ignores_day_of_month_but_not_approximations():
    g = grounding.check("Counted from 1 September to 30 September 2026 (June 30 too); rises of about £1,000.", [{"x": 1040.5}])
    assert g["ungrounded"] == ["£1,000"]


def test_grounding_accepts_ratio_shown_as_percent():
    g = grounding.check("232% of target time used; 130 outages", [{"elapsed_share": 2.32, "n": 44}])
    assert g["grounded"] == ["232%"] and g["ungrounded"] == ["130"]


def test_usage_is_per_answer_not_cumulative():
    fc = FakeClient([_resp("end_turn", [_text("a")]), _resp("end_turn", [_text("b")])])
    eng = ClaudeEngine(client=fc)
    a1 = ask("q1", "analyst.demo", engine=eng)
    a2 = ask("q2", "analyst.demo", engine=eng)
    assert a1.usage["requests"] == a2.usage["requests"] == 1 and a2.usage["input_tokens"] == 100


# ---------------------------------------------------------------- Claude engine with a scripted client

def _resp(stop, content):
    return SimpleNamespace(stop_reason=stop, content=content, usage=SimpleNamespace(input_tokens=100, output_tokens=20))


def _tool(id_, name, inp):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inp)


def _text(t):
    return SimpleNamespace(type="text", text=t)


class FakeClient:
    def __init__(self, script):
        self.script, self.calls = list(script), []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kw):
        self.calls.append(kw)
        return self.script.pop(0)


def test_claude_engine_tool_loop_records_evidence():
    fc = FakeClient([
        _resp("tool_use", [_tool("t1", "get_sla_breach_rate", {"period": "last_quarter", "group_by": "category"}),
                           _tool("t2", "nonexistent_tool", {})]),
        _resp("end_turn", [_text("Network had the highest breach rate at 27.2% [E1].")]),
    ])
    a = ask("Which category breached most?", "analyst.demo", engine=ClaudeEngine(client=fc))
    assert [e.tool for e in a.evidence] == ["get_sla_breach_rate", "nonexistent_tool"]
    assert a.evidence[1].is_error
    results = fc.calls[1]["messages"][-1]["content"]
    assert [r["tool_use_id"] for r in results] == ["t1", "t2"]          # both results in ONE user message
    assert results[1]["is_error"] is True
    assert 'trust="untrusted-data"' in results[0]["content"]
    assert a.grounding["ungrounded"] == []
    assert fc.calls[0]["fallbacks"] == "default" and fc.calls[0]["output_config"]["effort"]
    assert a.usage["requests"] == 2


def test_claude_engine_ungrounded_number_is_flagged():
    fc = FakeClient([_resp("end_turn", [_text("The breach rate was 41.3% last quarter.")])])
    a = ask("breach rate?", "analyst.demo", engine=ClaudeEngine(client=fc))
    assert a.grounding["ungrounded"] == ["41.3%"]


def test_claude_engine_cannot_reach_restricted_tools():
    fc = FakeClient([
        _resp("tool_use", [_tool("t1", "get_cost_change", {"month": "this_month", "group_by": "service"}),
                           _tool("t2", "run_sql", {"sql": "SELECT contact_email FROM customers"})]),
        _resp("end_turn", [_text(f"{ABSTAIN_PREFIX}: access denied.")]),
    ])
    a = ask("costs and customer emails", "desk.demo", engine=ClaudeEngine(client=fc))
    assert all(e.is_error for e in a.evidence) and a.abstained


def test_claude_engine_handles_refusal():
    fc = FakeClient([_resp("refusal", [])])
    a = ask("something", "analyst.demo", engine=ClaudeEngine(client=fc))
    assert a.abstained
