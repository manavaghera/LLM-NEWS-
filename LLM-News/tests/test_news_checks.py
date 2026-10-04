"""Claim check, coverage comparison and reliability scoring (fake LLM, no network). Run from LLM-News: python -m pytest tests"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))

from news_checks import claim_check, compare_coverage, split_sentences  # noqa: E402
from reliability import ReliabilityScorer, publisher_score  # noqa: E402

ITEMS = [
    {"publisher": "CBCNews", "region": "ca", "title": "UN extends Haiti force", "summary": "The mandate runs six months.",
     "link": "https://cbc.ca/1", "published": "2026-09-30"},
    {"publisher": "AlJazeera", "region": "qa", "title": "Haiti force mandate extended", "summary": "Gangs control the capital.",
     "link": "https://aljazeera.com/2", "published": "2026-09-30"},
]


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def generate(self, prompt_content, **kwargs):
        self.prompts.append(prompt_content)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(self.reply)))])


def test_split_sentences_keeps_abbreviations_and_citations():
    text = "The U.S. Supreme Court ruled.<a href='https://a/1'>[1]</a> Mr. Smith left. Rates fell 2.5% today"
    parts = split_sentences(text)
    assert len(parts) == 3 and "".join(parts) == text


def test_claim_check_removes_only_unsupported_sentences():
    article = {
        "lead": "The UN extended the force. It cost $5 billion.",
        "conclusion": "",
        "body": [
            {"section": "A", "content": "The mandate runs six months.<a href='https://cbc.ca/1'>[1]</a> The vote was 15-0.",
             "sources": ["https://cbc.ca/1"]},
            {"section": "B", "content": "Officials quoted a secret memo.", "sources": ["https://aljazeera.com/2"]},
        ],
        "timeline": {"2026-09-30": "Mandate extended", "2026-01-01": "Invented event"},
    }
    fake = FakeLLM({"unsupported": [{"id": "L.2", "reason": "no cost given"}, {"id": "S1.2", "reason": "no vote count"},
                                    {"id": "S2.1", "reason": "no memo"}, {"id": "T2", "reason": "not in items"},
                                    {"id": "Z9", "reason": "unknown id is ignored"}]})
    record = claim_check(article, ITEMS, fake, "m")
    assert article["lead"] == "The UN extended the force."
    assert article["body"] == [{"section": "A", "content": "The mandate runs six months.<a href='https://cbc.ca/1'>[1]</a>",
                                "sources": ["https://cbc.ca/1"]}]  # section B had nothing left
    assert article["timeline"] == {"2026-09-30": "Mandate extended"}
    assert record["checked"] and record["statements"] == 7 and len(record["removed"]) == 4
    assert "S1.2: The vote was 15-0." in fake.prompts[0]
    assert "[1] CBCNews, published 2026-09-30: UN extends Haiti force" in fake.prompts[0]  # timeline dates are checkable


def test_compare_coverage_keeps_only_real_outlets():
    fake = FakeLLM({"perspectives": [
        {"publisher": "CBCNews", "angle": "Leads with the vote", "tone": -0.2, "emphasis": "UN process", "not_mentioned": ["gangs"]},
        {"publisher": "AlJazeera", "angle": "Leads with gangs", "tone": -3, "emphasis": "security", "not_mentioned": []},
        {"publisher": "MadeUpNews", "angle": "x", "tone": 0},
    ], "common_ground": "Six-month extension", "differences": "Focus differs"})
    coverage = compare_coverage(ITEMS, fake, "m")
    assert [p["publisher"] for p in coverage["perspectives"]] == ["CBCNews", "AlJazeera"]
    assert coverage["perspectives"][1]["tone"] == -1.0  # clamped
    assert coverage["perspectives"][0]["links"] == ["https://cbc.ca/1"]
    assert compare_coverage(ITEMS[:1], fake, "m") is None  # one outlet: nothing to compare


def test_checks_retry_once_on_broken_json():
    replies = iter(["{not json", json.dumps({"unsupported": []})])

    class Flaky:
        calls = 0

        def generate(self, prompt_content, **kwargs):
            Flaky.calls += 1
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=next(replies)))])

    article = {"lead": "The UN extended the force.", "body": [{"section": "A", "content": "Six months.", "sources": []}]}
    assert claim_check(article, ITEMS, Flaky(), "m")["removed"] == []
    assert Flaky.calls == 2


def test_reliability_uses_trust_data_when_present(tmp_path):
    assert ReliabilityScorer(tmp_path).score_section("text", ["https://bbc.co.uk/x"]) == {}
    trust = tmp_path / "data" / "raw" / "trust_score"
    trust.mkdir(parents=True)
    (trust / "publishers_bias.csv").write_text(
        "Source URL,Bias,Factual Reporting,Credibility\nbbc.co.uk,Left-Center,High,High\n", encoding="utf-8")
    scorer = ReliabilityScorer(tmp_path)
    expected = publisher_score({"Bias": "Left-Center", "Factual Reporting": "High", "Credibility": "High"})
    assert expected == round(1.75 / 2 * 0.6 + 0.6 * 0.3 + 0.1, 3)
    assert scorer.score_section("text", ["https://www.bbc.co.uk/news/1"]) == {"publisher_reliability_score": expected}
    assert "publisher trust for 1 outlets" in scorer.status()
