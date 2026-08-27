"""JSON-safe serialization helpers.

pandas/numpy values (np.int64, np.float64, Timestamp, NaN) are not JSON /
msgpack serializable. Every object that crosses a boundary — tool results,
trace events, LangGraph interrupt payloads — must pass through json_safe().
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any


def json_safe(obj: Any) -> Any:
    """Recursively convert numpy/pandas scalars and other non-JSON types."""
    if obj is None:
        return None
    # pandas NA / numpy NaN
    try:
        import numpy as np

        if isinstance(obj, np.generic):
            if isinstance(obj, np.bool_):
                return bool(obj)
            if isinstance(obj, np.integer):
                return int(obj)
            if isinstance(obj, np.floating):
                v = float(obj)
                return None if math.isnan(v) or math.isinf(v) else v
            return obj.item()
        if isinstance(obj, np.ndarray):
            return json_safe(obj.tolist())
        if isinstance(obj, np.bool_):
            return bool(obj)
    except ImportError:
        pass
    if obj is None:
        return None
    if isinstance(obj, bool):
        return obj
    if isinstance(obj, (int, float, str)):
        if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
            return None
        return obj
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    # pandas Timestamp / NaT handled via date subclass; fallback:
    if hasattr(obj, "item"):
        try:
            return json_safe(obj.item())
        except (ValueError, TypeError):
            pass
    if hasattr(obj, "isoformat"):
        try:
            return obj.isoformat()
        except (ValueError, TypeError):
            pass
    return str(obj)
