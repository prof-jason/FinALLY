"""Parsing of structured LLM output, valid and malformed."""

import json

import pytest

from app.llm.schemas import ChatResponse, MalformedResponseError, parse_chat_response


def test_message_only():
    r = parse_chat_response('{"message": "Hello"}')
    assert r.message == "Hello"
    assert r.trades == [] and r.watchlist_changes == []


def test_full_schema():
    payload = {
        "message": "Placing orders.",
        "trades": [
            {"ticker": "AAPL", "side": "buy", "quantity": 10},
            {"ticker": "TSLA", "side": "sell", "quantity": 2.5},
        ],
        "watchlist_changes": [
            {"ticker": "PYPL", "action": "add"},
            {"ticker": "NFLX", "action": "remove"},
        ],
    }
    r = parse_chat_response(json.dumps(payload))
    assert [(t.ticker, t.side, t.quantity) for t in r.trades] == [
        ("AAPL", "buy", 10.0),
        ("TSLA", "sell", 2.5),
    ]
    assert [(c.ticker, c.action) for c in r.watchlist_changes] == [
        ("PYPL", "add"),
        ("NFLX", "remove"),
    ]


def test_empty_lists_and_nulls():
    r = parse_chat_response('{"message": "Hi", "trades": null, "watchlist_changes": []}')
    assert r.message == "Hi" and r.trades == [] and r.watchlist_changes == []


def test_only_trades():
    r = parse_chat_response(
        '{"message": "x", "trades": [{"ticker": "V", "side": "buy", "quantity": "3"}]}'
    )
    assert r.trades[0].quantity == 3.0


def test_code_fenced_json():
    content = 'Sure!\n```json\n{"message": "Fenced", "trades": []}\n```'
    assert parse_chat_response(content).message == "Fenced"


def test_json_embedded_in_prose():
    content = (
        'Here you go: {"message": "Embedded", "watchlist_changes": [{"ticker": "PYPL", '
        '"action": "add"}]} thanks'
    )
    r = parse_chat_response(content)
    assert r.message == "Embedded" and r.watchlist_changes[0].ticker == "PYPL"


def test_uppercase_enums_are_normalized():
    r = parse_chat_response(
        '{"message": "x", "trades": [{"ticker": "AAPL", "side": "BUY", '
        '"quantity": 1}], "watchlist_changes": [{"ticker": "V", '
        '"action": "Add"}]}'
    )
    assert r.trades[0].side == "buy" and r.watchlist_changes[0].action == "add"


def test_invalid_items_dropped_valid_kept():
    content = json.dumps(
        {
            "message": "Mixed",
            "trades": [
                {"ticker": "AAPL", "side": "hold", "quantity": 1},
                {"ticker": "MSFT"},
                "garbage",
                {"ticker": "TSLA", "side": "sell", "quantity": 1},
            ],
            "watchlist_changes": [{"ticker": "X", "action": "watch"}],
        }
    )
    r = parse_chat_response(content)
    assert [t.ticker for t in r.trades] == ["TSLA"]
    assert r.watchlist_changes == []


def test_single_trade_object_instead_of_list():
    r = parse_chat_response(
        '{"message": "x", "trades": {"ticker": "AAPL", "side": "buy", "quantity": 1}}'
    )
    assert len(r.trades) == 1


def test_plain_text_becomes_message():
    r = parse_chat_response("I think you should diversify.")
    assert r.message == "I think you should diversify." and r.trades == []


def test_truncated_json_falls_back_to_text():
    r = parse_chat_response('{"message": "cut off')
    assert r.message == '{"message": "cut off' and r.trades == []


@pytest.mark.parametrize("content", [None, "", "   "])
def test_empty_content_raises(content):
    with pytest.raises(MalformedResponseError):
        parse_chat_response(content)


def test_json_without_message_or_actions_raises():
    with pytest.raises(MalformedResponseError):
        parse_chat_response('{"foo": 1}')


def test_actions_without_message_ok():
    r = parse_chat_response('{"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}]}')
    assert r.message == "" and len(r.trades) == 1


def test_schema_has_required_fields_for_structured_output():
    schema = ChatResponse.model_json_schema()
    assert set(schema["properties"]) == {"message", "trades", "watchlist_changes"}
    assert "message" in schema["required"]
