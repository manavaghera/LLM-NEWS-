"""Topic extraction for Trends. Run from LLM-News/apps: python -m pytest tests"""
from app.services.topics import article_topics, broad_topics, extract_topics, shared_story_score


def test_finds_names_phrases_and_acronyms():
    text = ("Director Alejandro González Iñárritu spoke. The UN Security Council met, according to CBCNews. "
            "Police said the U.S. Supreme Court and OpenAI agreed with the Bank of England.")
    topics = extract_topics(text)
    assert {"UN Security Council", "U.S. Supreme Court", "OpenAI", "Bank of England"} <= topics
    assert any("González Iñárritu" in t for t in topics)


def test_skips_sentence_start_words_markup_and_fragments():
    topics = extract_topics("Five men were bailed. Police said more.<a href='https://www.bbc.co.uk/news'>[1]</a> "
                            "An Oscar-winning film. Reported by CBCNews.")
    assert topics == set()


def test_reporting_outlets_are_not_topics():
    articles = [{"lead": "", "body": [
        {"content": "Officials told BBC News and the Guardian that NATO met. CBC reported it too.",
         "Publishers": ["BBCNews", "TheGuardian", "CBCNews"]}]}]
    assert article_topics(articles) == {"NATO": 1}


def test_counts_stories_not_repetitions():
    articles = [
        {"lead": "The deal involves AMD. AMD and Nvidia compete.", "body": []},
        {"lead": "Shares of AMD rose.", "body": [{"content": "Analysts at Goldman Sachs agreed."}]},
        {"headline": "Title Case Headline Words Are Ignored", "lead": "", "body": []},
    ]
    assert article_topics(articles) == {"AMD": 2, "Nvidia": 1, "Goldman Sachs": 1}


def test_acronyms_with_numbers_and_outlet_ids():
    assert extract_topics("G7 leaders met before the G20 and COP30 talks.") == {"G7", "G20", "COP30"}
    articles = [{"lead": "", "body": [{"content": "The ArsTechnica article says Apple agreed.",
                                       "Publishers": ["ArsTechnica"]}]}]
    assert article_topics(articles) == {"Apple": 1}


def test_same_story_needs_a_specific_shared_topic():
    g7_today, g7_earlier = {"G7", "US", "Washington"}, {"G7", "US", "Iran"}
    assert shared_story_score(g7_today, g7_earlier) == 0                  # two plain names: not enough
    assert shared_story_score(g7_today, g7_earlier, strong={"G7"}) == 3   # "G7" leads both headlines
    assert shared_story_score({"UN Security Council", "Haiti"}, {"UN Security Council", "Haiti", "Kenya"}) == 3
    assert shared_story_score({"UN Security Council"}, {"UN Security Council"}) == 0  # one topic is never enough
    editions = [[{"US", "G7"}, {"US", "AI"}], [{"G7"}, {"AI", "Apple"}, {"AI"}]]
    assert broad_topics(editions) == {"US", "AI"}
