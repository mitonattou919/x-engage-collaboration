"""engage_client モジュールのユニットテスト"""
from unittest.mock import MagicMock, patch

import pytest
import requests

from engage_client import (
    FIELD_AUTHOR,
    FIELD_ID,
    FIELD_MEDIA_TYPE,
    FIELD_POST_URL,
    FIELD_TEXT,
    FIELD_TITLE,
    post_to_engage,
)


def _mock_response(status_code):
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = ""
    return resp


@patch("engage_client._SESSION")
def test_post_returns_true_on_200(mock_session):
    mock_session.post.return_value = _mock_response(200)
    assert post_to_engage("http://hook", "1", "user", "text", "2024-01-01", "http://url") is True


@patch("engage_client._SESSION")
def test_post_returns_true_on_202(mock_session):
    mock_session.post.return_value = _mock_response(202)
    assert post_to_engage("http://hook", "1", "user", "text", "2024-01-01", "http://url") is True


@patch("engage_client._SESSION")
def test_post_returns_false_on_4xx(mock_session):
    mock_session.post.return_value = _mock_response(400)
    assert post_to_engage("http://hook", "1", "user", "text", "2024-01-01", "http://url") is False


@patch("engage_client._SESSION")
def test_post_returns_false_on_5xx(mock_session):
    mock_session.post.return_value = _mock_response(500)
    assert post_to_engage("http://hook", "1", "user", "text", "2024-01-01", "http://url") is False


@patch("engage_client._SESSION")
def test_post_returns_false_on_request_exception(mock_session):
    mock_session.post.side_effect = requests.exceptions.RequestException("timeout")
    assert post_to_engage("http://hook", "1", "user", "text", "2024-01-01", "http://url") is False


@patch("engage_client._SESSION")
def test_payload_structure(mock_session):
    mock_session.post.return_value = _mock_response(200)
    post_to_engage("http://hook", "42", "alice", "tweet body", "2024-06-01T00:00:00Z", "http://x.com/alice/status/42")

    _, kwargs = mock_session.post.call_args
    payload = kwargs["json"]

    assert payload[FIELD_MEDIA_TYPE] == "twitter"
    assert payload[FIELD_ID] == "42"
    assert payload[FIELD_AUTHOR] == "@alice"
    assert payload[FIELD_TITLE] == "tweet"
    assert payload[FIELD_TEXT] == "tweet body"
    assert payload["published"] == "2024-06-01T00:00:00Z"
    assert payload[FIELD_POST_URL] == "http://x.com/alice/status/42"


@patch("engage_client._SESSION")
def test_author_at_prefix_not_duplicated(mock_session):
    """@ が既についている username でも @@ にならないことを確認"""
    mock_session.post.return_value = _mock_response(200)
    post_to_engage("http://hook", "1", "@alice", "text", "2024-01-01", "http://url")

    _, kwargs = mock_session.post.call_args
    assert kwargs["json"][FIELD_AUTHOR] == "@alice"
