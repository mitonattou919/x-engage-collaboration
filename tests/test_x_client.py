"""x_client モジュールのユニットテスト"""
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
import tweepy

import x_client
from x_client import Tweet, _tweet_url, fetch_new_tweets


@pytest.fixture(autouse=True)
def clear_user_id_cache():
    """各テスト前後にユーザーIDキャッシュをクリア"""
    x_client._user_id_cache.clear()
    yield
    x_client._user_id_cache.clear()


def _make_tweepy_client(user_id="111", tweets_data=None, user_found=True):
    """tweepy.Client のモックを生成するヘルパー"""
    mock_client = MagicMock()

    mock_user_resp = MagicMock()
    if user_found:
        mock_user_resp.data = MagicMock()
        mock_user_resp.data.id = user_id
    else:
        mock_user_resp.data = None
    mock_client.get_user.return_value = mock_user_resp

    mock_tweets_resp = MagicMock()
    mock_tweets_resp.data = tweets_data
    mock_client.get_users_tweets.return_value = mock_tweets_resp

    return mock_client


def _make_tweet_mock(tweet_id, text, created_at):
    t = MagicMock()
    t.id = tweet_id
    t.text = text
    t.created_at = created_at
    return t


# ---- _tweet_url ----

def test_tweet_url():
    assert _tweet_url("testuser", "123") == "https://x.com/testuser/status/123"


# ---- fetch_new_tweets: ユーザー解決失敗 ----

@patch("x_client.tweepy.Client")
def test_user_not_found_returns_empty(mock_cls):
    mock_cls.return_value = _make_tweepy_client(user_found=False)
    assert fetch_new_tweets("token", "unknown") == []


@patch("x_client.tweepy.Client")
def test_get_user_exception_returns_empty(mock_cls):
    mock_client = MagicMock()
    mock_client.get_user.side_effect = tweepy.TweepyException("error")
    mock_cls.return_value = mock_client
    assert fetch_new_tweets("token", "testuser") == []


# ---- fetch_new_tweets: ツイート取得失敗 ----

@patch("x_client.tweepy.Client")
def test_rate_limit_returns_empty(mock_cls):
    mock_client = _make_tweepy_client()
    mock_client.get_users_tweets.side_effect = tweepy.TooManyRequests(MagicMock())
    mock_cls.return_value = mock_client
    assert fetch_new_tweets("token", "testuser") == []


@patch("x_client.tweepy.Client")
def test_tweepy_exception_on_tweets_returns_empty(mock_cls):
    mock_client = _make_tweepy_client()
    mock_client.get_users_tweets.side_effect = tweepy.TweepyException("error")
    mock_cls.return_value = mock_client
    assert fetch_new_tweets("token", "testuser") == []


@patch("x_client.tweepy.Client")
def test_no_new_tweets_returns_empty(mock_cls):
    mock_cls.return_value = _make_tweepy_client(tweets_data=None)
    assert fetch_new_tweets("token", "testuser") == []


# ---- fetch_new_tweets: 正常系 ----

@patch("x_client.tweepy.Client")
def test_returns_tweets_oldest_first(mock_cls):
    """X API は新しい順で返すため、逆順（古い順）になることを確認"""
    newer = _make_tweet_mock("200", "newer", datetime(2024, 1, 2))
    older = _make_tweet_mock("100", "older", datetime(2024, 1, 1))
    mock_cls.return_value = _make_tweepy_client(tweets_data=[newer, older])

    result = fetch_new_tweets("token", "testuser")

    assert len(result) == 2
    assert result[0].tweet_id == "100"
    assert result[1].tweet_id == "200"


@patch("x_client.tweepy.Client")
def test_tweet_fields_populated(mock_cls):
    t = _make_tweet_mock("999", "hello world", datetime(2024, 6, 1))
    mock_cls.return_value = _make_tweepy_client(tweets_data=[t])

    result = fetch_new_tweets("token", "alice")

    assert len(result) == 1
    assert result[0].tweet_id == "999"
    assert result[0].text == "hello world"
    assert result[0].author_username == "alice"
    assert result[0].url == "https://x.com/alice/status/999"


@patch("x_client.tweepy.Client")
def test_since_id_passed_to_api(mock_cls):
    mock_cls.return_value = _make_tweepy_client(tweets_data=None)
    fetch_new_tweets("token", "testuser", since_id="777")
    _, kwargs = mock_cls.return_value.get_users_tweets.call_args
    assert kwargs["since_id"] == "777"


# ---- キャッシュ ----

@patch("x_client.tweepy.Client")
def test_user_id_cached_across_calls(mock_cls):
    mock_client = _make_tweepy_client(tweets_data=None)
    mock_cls.return_value = mock_client

    fetch_new_tweets("token", "testuser")
    fetch_new_tweets("token", "testuser")

    # 2回呼んでも get_user は1回だけ
    assert mock_client.get_user.call_count == 1
