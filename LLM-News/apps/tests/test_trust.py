"""Accuracy tracking, reader reports and earlier coverage. Run from LLM-News/apps: python -m pytest tests"""
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from fastapi.testclient import TestClient

from app.core import limits
from app.main import app
from conftest import write_article

client = TestClient(app)


def set_article(path, **fields):
    article = json.loads(path.read_text(encoding="utf-8"))
    article.update(fields)
    path.write_text(json.dumps(article), encoding="utf-8")


def test_accuracy_counts_removed_statements_per_day_and_model(static_root):
    a = write_article(static_root, "2026-01-02", "group_1", "Checked")
    set_article(a, generated_by="quick_news (OPENROUTER / writer-model)",
                claim_check={"checked": True, "statements": 10, "removed": [{"text": "x", "reason": "y"}] * 3, "model": "checker-model"})
    b = write_article(static_root, "2026-01-02", "group_2", "Also checked")
    set_article(b, generated_by="quick_news (OPENROUTER / writer-model)",
                claim_check={"checked": True, "statements": 10, "removed": [], "model": "checker-model"})
    write_article(static_root, "2026-01-01", "group_1", "Older, never checked")

    body = client.get("/api/trends/accuracy").json()
    assert [(d["date"], d["checked"], d["statements"], d["removed"], d["removed_pct"]) for d in body["days"]] == [
        ("2026-01-01", 0, 0, 0, None), ("2026-01-02", 2, 20, 3, 15.0)]
    assert body["models"] == [{"writer": "writer-model", "checker": "checker-model", "articles": 2,
                               "statements": 20, "removed": 3, "removed_pct": 15.0}]


def test_reader_report_is_stored_without_personal_data(static_root, monkeypatch):
    write_article(static_root, "2026-01-01", "group_1", "Story")
    response = client.post("/api/reports", json={"date": "2026-01-01", "group_id": "group_1",
                                                 "kind": "wrong_fact", "message": "The vote was 14-1, not 15-0."})
    assert response.status_code == 201
    columns = [c[1] for c in sqlite3.connect(static_root / "cache" / "reports.db").execute("PRAGMA table_info(reports)")]
    assert columns == ["id", "created_at", "date", "group_id", "kind", "message"]  # no IP or identity
    assert client.get("/api/trends/accuracy").json()["days"][0]["reader_reports"] == 1


def test_reader_reports_are_validated_and_rate_limited(static_root, monkeypatch):
    from app.api.endpoints import reports
    write_article(static_root, "2026-01-01", "group_1", "Story")
    ok = {"date": "2026-01-01", "group_id": "group_1", "kind": "other", "message": "Typo in the lead."}
    assert client.post("/api/reports", json={**ok, "kind": "spam"}).status_code == 422
    assert client.post("/api/reports", json={**ok, "message": "x"}).status_code == 422
    assert client.post("/api/reports", json={**ok, "group_id": "group_9"}).status_code == 404

    monkeypatch.setattr(reports, "report_limiter", limits.RateLimiter(limit=2))
    assert [client.post("/api/reports", json=ok).status_code for _ in range(3)] == [201, 201, 429]


def test_report_list_needs_the_admin_token(static_root, monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    assert client.get("/api/reports").status_code == 404  # no token configured: hidden
    monkeypatch.setenv("ADMIN_TOKEN", "s3cret")
    assert client.get("/api/reports", headers={"X-Admin-Token": "wrong"}).status_code == 404
    assert client.get("/api/reports", headers={"X-Admin-Token": "s3cret"}).json() == {"reports": []}


def test_earlier_coverage_links_the_same_running_story(static_root):
    today = write_article(static_root, "2026-01-03", "group_1", "Haiti vote")
    set_article(today, lead="The UN Security Council extended the Haiti mission run by Kenya.")
    same = write_article(static_root, "2026-01-01", "group_1", "Earlier Haiti vote")
    set_article(same, lead="The UN Security Council debated the Haiti mission led by Kenya.")
    unrelated = write_article(static_root, "2026-01-02", "group_1", "Kenya marathon")
    set_article(unrelated, lead="A runner from Kenya won the marathon.")  # one shared name is not enough

    related = client.get("/api/news/articles/2026-01-03/group_1/related").json()
    assert [(r["date"], r["group_id"]) for r in related] == [("2026-01-01", "group_1")]
    assert related[0]["shared_topics"][0] == "UN Security Council"
    assert client.get("/api/news/articles/2026-01-01/group_1/related").json() == []  # only looks back


def test_earlier_coverage_by_a_shared_headline_subject(static_root):
    today = write_article(static_root, "2026-01-03", "group_1", "G7 Prepares to Release Oil Reserves")
    set_article(today, lead="Under pressure from Washington, the G7 agreed to release oil, avoiding a US export ban.")
    same = write_article(static_root, "2026-01-02", "group_1", "G7 Agrees to Release 100 Million Barrels")
    set_article(same, lead="The G7 will release oil after fighting between the US and Iran.")
    other = write_article(static_root, "2026-01-02", "group_2", "Five Men Released on Bail")
    set_article(other, lead="Police said the men worked for Iran and had links to the US.")  # names, not subject

    related = client.get("/api/news/articles/2026-01-03/group_1/related").json()
    assert [(r["date"], r["group_id"]) for r in related] == [("2026-01-02", "group_1")]
    assert related[0]["shared_topics"] == ["G7", "US"]


def test_earlier_coverage_counts_headline_names_the_body_only_starts_a_sentence_with(static_root):
    today = write_article(static_root, "2026-01-03", "group_1", "Brazil's Election Pits Lula Against Flávio Bolsonaro")
    set_article(today, lead="Polls are close. Brazil's voters choose between Lula and Flávio Bolsonaro.")
    before = write_article(static_root, "2026-01-02", "group_1", "Brazil's Presidential Election Shapes Up")
    set_article(before, lead="The vote in Brazil is a test for Lula and the right.")

    related = client.get("/api/news/articles/2026-01-03/group_1/related").json()
    assert [(r["date"], r["group_id"]) for r in related] == [("2026-01-02", "group_1")]
    assert related[0]["shared_topics"] == ["Brazil", "Lula"]


def create_owner_report(static_root, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "owner-secret")
    write_article(static_root, "2026-01-01", "group_1", "Story")
    response = client.post("/api/reports", json={"date": "2026-01-01", "group_id": "group_1",
                                                 "kind": "wrong_fact", "message": "Private reader message"})
    assert response.status_code == 201
    headers = {"X-Admin-Token": "owner-secret"}
    report = client.get("/api/reports", headers=headers).json()["reports"][0]
    return headers, report


def test_owner_can_resolve_dismiss_and_reopen_reports(static_root, monkeypatch):
    headers, report = create_owner_report(static_root, monkeypatch)
    assert (report["status"], report["resolution"], report["resolved_at"]) == ("open", "", None)
    url = f"/api/reports/{report['id']}"
    for status in ("resolved", "dismissed", "open"):
        response = client.patch(url, headers=headers, json={"status": status, "resolution": "Reviewed sources"})
        assert response.status_code == 200
        updated = response.json()["report"]
        assert updated["status"] == status and updated["resolution"] == "Reviewed sources"
        assert bool(updated["resolved_at"]) == (status != "open")
    assert client.get("/api/reports", headers=headers).json()["reports"][0]["status"] == "open"


def test_corrections_are_public_dated_and_retry_safe(static_root, monkeypatch):
    headers, report = create_owner_report(static_root, monkeypatch)
    payload = {"text": "Correction: the recorded vote was 14–1."}
    url = f"/api/reports/{report['id']}/correction"
    first = client.post(url, headers=headers, json=payload)
    retried = client.post(url, headers=headers, json=payload)
    assert first.status_code == retried.status_code == 201
    assert first.json() == retried.json()
    public = client.get("/api/reports/corrections/2026-01-01/group_1")
    notes = public.json()["corrections"]
    assert notes == [first.json()["correction"]]
    assert set(notes[0]) == {"id", "created_at", "text"}
    assert notes[0]["created_at"].endswith("+00:00")
    assert "Private reader message" not in public.text
    assert client.get("/api/reports/corrections/2026-01-01/group_2").json() == {"corrections": []}
    saved = client.get("/api/reports", headers=headers).json()["reports"][0]
    assert saved["status"] == "resolved" and saved["resolution"] == payload["text"]


def test_report_mutations_require_auth_and_validate_requests(static_root, monkeypatch):
    headers, report = create_owner_report(static_root, monkeypatch)
    url = f"/api/reports/{report['id']}"
    for auth in ({}, {"X-Admin-Token": "wrong"}):
        assert client.patch(url, headers=auth, json={"status": "resolved"}).status_code == 404
        assert client.post(url + "/correction", headers=auth, json={"text": "A public correction"}).status_code == 404
    assert client.patch(url, headers=headers, json={"status": "invalid"}).status_code == 422
    assert client.patch(url, headers=headers, json={"status": "resolved", "resolution": "x" * 2001}).status_code == 422
    for text in ("     ", "x" * 3001):
        assert client.post(url + "/correction", headers=headers, json={"text": text}).status_code == 422
    assert client.patch("/api/reports/999", headers=headers, json={"status": "resolved"}).status_code == 404
    assert client.post("/api/reports/999/correction", headers=headers, json={"text": "A public correction"}).status_code == 404
    assert client.get("/api/reports/corrections/invalid/group_1").status_code == 422


def test_existing_report_database_adds_review_tables_without_altering_reports(static_root):
    from app.services.report_service import ReportService
    database = static_root / "cache" / "reports.db"
    database.parent.mkdir()
    with sqlite3.connect(database) as db:
        db.execute("""CREATE TABLE reports (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
                      date TEXT NOT NULL, group_id TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL)""")
        db.execute("INSERT INTO reports VALUES (1, '2026-01-01', '2026-01-01', 'group_1', 'other', 'Older report')")
    service = ReportService()
    assert service.latest()[0]["status"] == "open"
    with sqlite3.connect(database) as db:
        assert [row[1] for row in db.execute("PRAGMA table_info(reports)")] == [
            "id", "created_at", "date", "group_id", "kind", "message"]


def test_concurrent_correction_retries_only_publish_once(static_root, monkeypatch):
    from app.services.report_service import ReportService
    headers, report = create_owner_report(static_root, monkeypatch)
    with ThreadPoolExecutor(max_workers=2) as pool:
        notes = list(pool.map(lambda _: ReportService().publish_correction(report["id"], "The vote was 14–1."), range(2)))
    assert notes[0] == notes[1]
    assert len(client.get("/api/reports/corrections/2026-01-01/group_1").json()["corrections"]) == 1


def test_report_storage_errors_have_generic_responses(static_root, monkeypatch):
    from app.api.endpoints import reports
    headers, report = create_owner_report(static_root, monkeypatch)

    def fail(*args):
        raise RuntimeError("private database details")

    monkeypatch.setattr(reports.report_service, "publish_correction", fail)
    response = client.post(f"/api/reports/{report['id']}/correction", headers=headers,
                           json={"text": "A public correction"})
    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to publish correction"}


def test_corrections_stay_with_original_story_across_edits_but_not_replacements(static_root, monkeypatch):
    headers, report = create_owner_report(static_root, monkeypatch)
    assert report["article_matches"] is True and report["original_headline"] == "Story"
    url = f"/api/reports/{report['id']}/correction"
    assert client.post(url, headers=headers, json={"text": "A correction for the original story"}).status_code == 201
    path = static_root / "static" / "articles" / "2026-01-01" / "group_1.json"
    set_article(path, headline="Story with an edited headline", lead="A corrected factual paragraph")
    public = "/api/reports/corrections/2026-01-01/group_1"
    assert len(client.get(public).json()["corrections"]) == 1  # same source identity survives text edits
    set_article(path, headline="Unrelated replacement", body=[{"content": "Different news", "sources": ["https://other.example/new"]}])
    assert client.get(public).json() == {"corrections": []}
    current = client.get("/api/reports", headers=headers).json()["reports"][0]
    assert current["original_headline"] == "Story" and current["article_matches"] is False
    assert client.post(url, headers=headers, json={"text": "Must not be attached to the replacement"}).status_code == 409


def test_legacy_unbound_report_cannot_publish_or_expose_corrections(static_root, monkeypatch):
    from app.services.report_service import ReportService
    monkeypatch.setenv("ADMIN_TOKEN", "owner-secret")
    write_article(static_root, "2026-01-01", "group_1", "A current story")
    service = ReportService()
    report_id = service.add("2026-01-01", "group_1", "other", "Legacy report without original source identity")
    with sqlite3.connect(service.path) as db:
        db.execute("INSERT INTO corrections(report_id,created_at,text) VALUES (?, ?, ?)",
                   (report_id, "2026-01-01T12:00:00+00:00", "An old unbound note"))
    assert client.get("/api/reports/corrections/2026-01-01/group_1").json() == {"corrections": []}
    response = client.post(f"/api/reports/{report_id}/correction", headers={"X-Admin-Token": "owner-secret"},
                           json={"text": "A new note cannot safely bind the old report"})
    assert response.status_code == 409


def followed_article(root, date, group_id, headline, lead):
    path = write_article(root, date, group_id, headline)
    set_article(path, lead=lead, body=[{"content": "Reported facts", "sources": [f"https://example.com/{date}/{group_id}"]}])
    return path


def test_followed_story_updates_include_only_later_matching_deduplicated_coverage(static_root):
    baseline = followed_article(static_root, "2026-01-02", "group_2", "Haiti mission vote",
                                "The UN Security Council debated the Haiti mission run by Kenya.")
    followed_article(static_root, "2026-01-02", "group_1", "Earlier same-day story",
                     "The UN Security Council discussed the Haiti mission led by Kenya.")
    followed_article(static_root, "2026-01-02", "group_10", "Later same-day vote",
                     "The UN Security Council extended the Haiti mission led by Kenya.")
    update = followed_article(static_root, "2026-01-03", "group_1", "Haiti mission extended",
                              "The UN Security Council renewed the Haiti mission led by Kenya.")
    duplicate = write_article(static_root, "2026-01-04", "group_1", "Duplicate publication")
    duplicate.write_text(update.read_text())
    followed_article(static_root, "2026-01-04", "group_2", "Kenya marathon",
                     "A runner from Kenya won a race in Nairobi.")
    response = client.get("/api/news/articles/2026-01-02/group_2/updates")
    assert response.status_code == 200
    body = response.json()
    assert [(u["date"], u["group_id"]) for u in body["updates"]] == [
        ("2026-01-04", "group_1"), ("2026-01-02", "group_10")]
    assert all(u["shared_topics"] and len(u["content_version"]) == 64 and len(u["story_identity"]) == 64
               for u in body["updates"])
    article = client.get("/api/news/articles/2026-01-02/group_2").json()
    assert (body["content_version"], body["story_identity"]) == (article["content_version"], article["story_identity"])
    assert len(client.get("/api/news/articles/2026-01-02/group_2/updates?limit=1").json()["updates"]) == 1
    assert client.get("/api/news/articles/2026-01-02/group_99/updates").status_code == 404
    assert client.get("/api/news/articles/invalid/group_2/updates").status_code == 422
    assert client.get("/api/news/articles/2026-01-02/group_2/updates?limit=21").status_code == 422


@pytest.mark.parametrize("subject,expected", [("G7", 1), ("AI", 0)])
def test_same_edition_updates_keep_specific_headline_subjects_but_reject_generic_topics(static_root, subject, expected):
    followed_article(static_root, "2026-01-02", "group_1", f"{subject} prepares a plan",
                     f"The leaders discussed {subject} and US policy.")
    followed_article(static_root, "2026-01-02", "group_2", f"{subject} announces a decision",
                     f"The officials reviewed {subject} and US policy.")
    assert len(client.get("/api/news/articles/2026-01-02/group_1/updates").json()["updates"]) == expected


def test_material_versions_ignore_media_metadata_but_detect_facts_and_corrections(static_root, monkeypatch):
    headers, report = create_owner_report(static_root, monkeypatch)
    url = "/api/news/articles/2026-01-01/group_1/updates"
    path = static_root / "static" / "articles" / "2026-01-01" / "group_1.json"
    first = client.get(url).json()
    set_article(path, image_file="group_1.webp", summary_speech="New narration", generated_by="another model",
                added_at="2026-01-01T15:00:00+00:00", claim_check={"checked": True})
    metadata = client.get(url).json()
    assert (metadata["content_version"], metadata["story_identity"]) == (first["content_version"], first["story_identity"])
    set_article(path, lead="The vote was actually 14–1.")
    factual = client.get(url).json()
    assert factual["content_version"] != first["content_version"] and factual["story_identity"] == first["story_identity"]
    assert client.post(f"/api/reports/{report['id']}/correction", headers=headers,
                       json={"text": "Correction: the earlier vote total was incorrect."}).status_code == 201
    corrected = client.get(url).json()
    assert corrected["content_version"] != factual["content_version"] and corrected["story_identity"] == factual["story_identity"]
    set_article(path, body=[{"content": "An unrelated replacement", "sources": ["https://different.example/story"]}])
    assert client.get(url).json()["story_identity"] != corrected["story_identity"]


def test_updates_scan_is_bounded_to_newest_thirty_later_editions(static_root):
    from datetime import date, timedelta
    base = date(2026, 1, 1)
    followed_article(static_root, base.isoformat(), "group_1", "Haiti mission",
                     "The UN Security Council debated the Haiti mission.")
    for offset in range(1, 33):
        day = (base + timedelta(days=offset)).isoformat()
        followed_article(static_root, day, "group_1", f"Haiti mission day {offset}",
                         f"The UN Security Council debated the Haiti mission on day {offset}.")
    updates = client.get(f"/api/news/articles/{base.isoformat()}/group_1/updates").json()["updates"]
    assert len(updates) == 20
    assert updates[0]["date"] == (base + timedelta(days=32)).isoformat()
    from app.api.endpoints.news import news_service
    from app.services.archive import story_updates
    all_updates = story_updates(news_service, base.isoformat(), "group_1", limit=40)
    assert len(all_updates["updates"]) == 30
