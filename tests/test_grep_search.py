import os
from utim_cli.tools import grep_search

def test_grep_search_auto_regex_pipe():
    # Test pipe alternation auto-detection without is_regex=True
    res = grep_search("laguna-s-2.1|gemma-4-26b|gpt-oss-20b", path="landing/src/pages/RewardsPage.jsx")
    assert "Search Results for" in res
    assert "laguna-s-2.1" in res or "gemma-4-26b" in res or "gpt-oss-20b" in res
