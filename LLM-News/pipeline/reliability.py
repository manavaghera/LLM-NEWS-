"""Reliability scores for quick_news sections, from the project's own data when it exists.

- Publisher trust: data/raw/trust_score/publishers_bias.csv (run scrapers/trust_score/publishers_bias_scraper.py),
  scored with the same formula as card/event/process.py.
- Fake-news probability: the trained classifier (python classifier/fake_news/run_pipeline.py).

When neither is available nothing is added, and the website shows "Not scored" rather than a guess.
"""
import csv
from pathlib import Path
from typing import Dict, List, Optional

BIAS = {
    "Left": -0.8, "Left-Center": -0.4, "Least Biased": 0.0, "Right-Center": 0.4, "Right": 0.8,
    "Conspiracy-Pseudoscience": -0.9, "Questionable": 0.9, "Satire": 0.0, "Pro-Science": -0.3,
}
FACTUAL = {"Very High": 1.0, "High": 0.75, "Mostly Factual": 0.5, "Mixed": 0.0, "Low": -0.5, "Very Low": -1.0}
CREDIBILITY = {"High": 1.0, "Medium": 0.5, "Low": -1.0}

PUBLISHER_FILE = Path("data/raw/trust_score/publishers_bias.csv")
CLASSIFIER_FILE = Path("classifier/fake_news/models/results/random_forest_model.joblib")


def publisher_score(row: Dict[str, str]) -> Optional[float]:
    """0-1 trust score: factual reporting 60%, low bias 30%, credibility 10% (as in card/event/process.py)"""
    bias = BIAS.get((row.get("Bias") or "").strip())
    if bias is None:
        return None
    factual = FACTUAL.get((row.get("Factual Reporting") or "").strip(), 0.0)
    credibility = CREDIBILITY.get((row.get("Credibility") or "").strip().capitalize(), 0.0)
    return round((factual + 1) / 2 * 0.6 + (1 - abs(bias)) * 0.3 + (credibility + 1) / 2 * 0.1, 3)


class ReliabilityScorer:
    def __init__(self, root: Path):
        self.publishers: Dict[str, float] = {}
        path = root / PUBLISHER_FILE
        if path.exists():
            with open(path, encoding="utf-8", errors="replace", newline="") as f:
                for row in csv.DictReader(f):
                    score, source = publisher_score(row), (row.get("Source URL") or "").strip()
                    if source and score is not None:
                        self.publishers[source] = score

        self.classifier = None
        self.classifier_error = ""
        if (root / CLASSIFIER_FILE).exists():
            try:
                from classifier.fake_news.predict import FakeNewsPredictor
                self.classifier = FakeNewsPredictor(str(root / CLASSIFIER_FILE))
            except Exception as e:  # missing packages (pandas, nltk...) or an incompatible model
                self.classifier_error = str(e)

    def status(self) -> str:
        parts = [f"publisher trust for {len(self.publishers)} outlets" if self.publishers else "",
                 "fake-news classifier" if self.classifier else ""]
        found = [p for p in parts if p]
        if found:
            return "Reliability: " + " + ".join(found)
        hint = f" (classifier failed to load: {self.classifier_error[:80]})" if self.classifier_error else ""
        return ("Reliability: not scored. Add data/raw/trust_score/publishers_bias.csv or train "
                "classifier/fake_news to enable it" + hint)

    def score_section(self, text: str, links: List[str]) -> Dict[str, float]:
        """Fields to add to one article section (empty when nothing can be scored)"""
        scores: Dict[str, float] = {}
        matched = [score for link in links for source, score in self.publishers.items() if source in link]
        if matched:
            scores["publisher_reliability_score"] = round(sum(matched) / len(matched), 3)
        if self.classifier and text.strip():
            try:
                scores["fake_news_probability"] = round(self.classifier.predict(text)["fake_probability"], 3)
            except Exception:
                pass
        return scores
