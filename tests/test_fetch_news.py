import unittest
from types import SimpleNamespace

import fetch_news


class ScopeFilterTests(unittest.TestCase):
    def test_us_domestic_entry_with_non_americas_keyword_is_kept(self):
        entry = SimpleNamespace(
            title="US Congress passes China tariff bill",
            summary="Congress approved a tariff package as part of a domestic economic policy debate.",
            link="https://example.com/us-congress-china-tariff-bill",
        )

        self.assertIsNone(fetch_news.get_scope_exclusion_reason(entry))

    def test_non_americas_topic_without_valid_scope_is_excluded(self):
        entry = SimpleNamespace(
            title="China and Russia hold talks on Ukraine",
            summary="Beijing and Moscow discussed Ukraine and European security policy.",
            link="https://example.com/world/china-russia-ukraine",
        )

        self.assertEqual(fetch_news.get_scope_exclusion_reason(entry), "非美洲主题")


class CandidateDeduplicationTests(unittest.TestCase):
    def test_google_news_source_suffix_is_removed_before_title_deduplication(self):
        direct_rss_entry = SimpleNamespace(
            title="Foo bar",
            link="https://www.bbc.com/news/articles/example-story",
            source={"title": "BBC"},
            feed_name="BBC US & Canada",
        )
        google_news_entry = SimpleNamespace(
            title="Foo bar - BBC",
            link="https://news.google.com/rss/articles/example-story",
            source={
                "title": "BBC",
                "href": "https://www.bbc.com/news/articles/example-story?utm_source=google-news",
            },
            feed_name="Google News - Major Americas",
            source_info="Google News",
        )

        deduplicated = fetch_news.deduplicate_candidate_entries([
            direct_rss_entry,
            google_news_entry,
        ])

        self.assertEqual(deduplicated, [direct_rss_entry])


if __name__ == "__main__":
    unittest.main()
