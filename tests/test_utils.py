import pandas as pd
from src.polygon_utils import normalize_polygon_ticker, session_mask

def test_normalize_polygon_ticker():
    assert normalize_polygon_ticker("brk-b") == "BRK.B"
    assert normalize_polygon_ticker("BRK.B") == "BRK.B"
    assert normalize_polygon_ticker(" aapl ") == "AAPL"

def test_session_mask_basic():
    # build a tiny index covering pre, regular, post
    tz = "America/New_York"
    ts = pd.to_datetime([
        "2024-05-06 09:29", "2024-05-06 09:30", "2024-05-06 12:00",
        "2024-05-06 16:00", "2024-05-06 16:01"
    ]).tz_localize(tz)
    m = session_mask(pd.Series(ts))
    # Only 09:30–16:00 inclusive are True
    assert m.tolist() == [False, True, True, True, False]
