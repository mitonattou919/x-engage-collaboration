"""function_app のオーケストレーションロジックのユニットテスト"""
from unittest.mock import MagicMock, patch

import pytest

from function_app import fetch_and_post_tweets


def _make_timer(past_due=False):
    timer = MagicMock()
    timer.past_due = past_due
    return timer


def _make_tweet(tweet_id, username="testuser", text="hello"):
    from x_client import Tweet
    return Tweet(
        tweet_id=tweet_id,
        author_username=username,
        text=text,
        created_at="2024-01-01T00:00:00+00:00",
        url=f"https://x.com/{username}/status/{tweet_id}",
    )


@patch("function_app.post_to_engage")
@patch("function_app.get_secret")
def test_secret_fetch_failure_returns_early(mock_get_secret, mock_post):
    mock_get_secret.side_effect = Exception("vault error")
    fetch_and_post_tweets(_make_timer())
    # 例外が外に漏れず、かつ後続処理が呼ばれないことを確認
    mock_post.assert_not_called()


@patch("function_app.fetch_new_tweets", return_value=[])
@patch("function_app.get_secret", return_value="mock-secret")
def test_empty_x_accounts_returns_early(mock_secret, mock_fetch, monkeypatch):
    monkeypatch.setenv("X_ACCOUNTS", "")
    fetch_and_post_tweets(_make_timer())
    mock_fetch.assert_not_called()


@patch("function_app.fetch_new_tweets", return_value=[])
@patch("function_app.get_secret", return_value="mock-secret")
def test_no_new_tweets_skips_post(mock_secret, mock_fetch, monkeypatch):
    monkeypatch.setenv("X_ACCOUNTS", "alice")
    with patch("function_app.post_to_engage") as mock_post:
        fetch_and_post_tweets(_make_timer())
    mock_post.assert_not_called()


@patch("function_app.set_last_tweet_id")
@patch("function_app.get_last_tweet_id", return_value=None)
@patch("function_app.post_to_engage", return_value=True)
@patch("function_app.fetch_new_tweets")
@patch("function_app.get_secret", return_value="mock-secret")
def test_successful_post_updates_last_tweet_id(
    mock_secret, mock_fetch, mock_post, mock_get_id, mock_set_id, monkeypatch
):
    monkeypatch.setenv("X_ACCOUNTS", "alice")
    mock_fetch.return_value = [_make_tweet("100", "alice"), _make_tweet("200", "alice")]

    fetch_and_post_tweets(_make_timer())

    # 最後に成功したツイートIDで更新されること
    mock_set_id.assert_called_once_with("alice", "200")


@patch("function_app.set_last_tweet_id")
@patch("function_app.get_last_tweet_id", return_value=None)
@patch("function_app.post_to_engage")
@patch("function_app.fetch_new_tweets")
@patch("function_app.get_secret", return_value="mock-secret")
def test_post_failure_stops_remaining_tweets(
    mock_secret, mock_fetch, mock_post, mock_get_id, mock_set_id, monkeypatch
):
    """1件目失敗 → 残りをスキップし last_tweet_id を更新しない"""
    monkeypatch.setenv("X_ACCOUNTS", "alice")
    mock_fetch.return_value = [_make_tweet("100", "alice"), _make_tweet("200", "alice")]
    mock_post.return_value = False

    fetch_and_post_tweets(_make_timer())

    # 1件目だけ試みて止まる
    assert mock_post.call_count == 1
    mock_set_id.assert_not_called()


@patch("function_app.set_last_tweet_id")
@patch("function_app.get_last_tweet_id", return_value=None)
@patch("function_app.post_to_engage")
@patch("function_app.fetch_new_tweets")
@patch("function_app.get_secret", return_value="mock-secret")
def test_partial_success_saves_last_successful_id(
    mock_secret, mock_fetch, mock_post, mock_get_id, mock_set_id, monkeypatch
):
    """1件目成功・2件目失敗 → 1件目の ID で保存"""
    monkeypatch.setenv("X_ACCOUNTS", "alice")
    mock_fetch.return_value = [_make_tweet("100", "alice"), _make_tweet("200", "alice")]
    mock_post.side_effect = [True, False]

    fetch_and_post_tweets(_make_timer())

    mock_set_id.assert_called_once_with("alice", "100")


@patch("function_app.fetch_new_tweets", return_value=[])
@patch("function_app.get_secret", return_value="mock-secret")
def test_past_due_logs_warning(mock_secret, mock_fetch, monkeypatch, caplog):
    import logging
    monkeypatch.setenv("X_ACCOUNTS", "alice")
    with caplog.at_level(logging.WARNING, logger="function_app"):
        fetch_and_post_tweets(_make_timer(past_due=True))
    assert any("遅延" in r.message for r in caplog.records)


@patch("function_app.set_last_tweet_id")
@patch("function_app.get_last_tweet_id", return_value=None)
@patch("function_app.post_to_engage", return_value=True)
@patch("function_app.fetch_new_tweets")
@patch("function_app.get_secret", return_value="mock-secret")
def test_multiple_accounts_processed_independently(
    mock_secret, mock_fetch, mock_post, mock_get_id, mock_set_id, monkeypatch
):
    """複数アカウントがそれぞれ独立して処理されること"""
    monkeypatch.setenv("X_ACCOUNTS", "alice,bob")
    mock_fetch.side_effect = [
        [_make_tweet("100", "alice")],
        [_make_tweet("200", "bob")],
    ]

    fetch_and_post_tweets(_make_timer())

    assert mock_post.call_count == 2
    mock_set_id.assert_any_call("alice", "100")
    mock_set_id.assert_any_call("bob", "200")
