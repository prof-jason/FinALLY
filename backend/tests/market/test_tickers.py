import pytest

from app.market.tickers import InvalidTickerError, UnknownTickerError, normalize_ticker


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("AAPL", "AAPL"), ("aapl", "AAPL"), (" msft ", "MSFT"), ("V", "V"), ("googl", "GOOGL")],
)
def test_normalize_valid(raw, expected):
    assert normalize_ticker(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "   ", "TOOLONG", "BRK.B", "AB1", "A-B", "ÄPPL", "A B", None, 123]
)
def test_normalize_invalid(raw):
    with pytest.raises(InvalidTickerError):
        normalize_ticker(raw)


def test_invalid_ticker_is_value_error():
    assert issubclass(InvalidTickerError, ValueError)


def test_unknown_ticker_message():
    err = UnknownTickerError("XYZ")
    assert str(err) == "Unknown ticker: XYZ"
    assert err.ticker == "XYZ"
