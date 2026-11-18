"""JSON helpers shared by jobs and the API."""
import json
import math
from datetime import datetime

import numpy as np
import pandas as pd


def jsonable(obj):
    """Plain JSON types; NaN/inf become null so no number is invented."""
    def fix(o):
        if isinstance(o, dict):
            return {str(k): fix(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [fix(v) for v in o]
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating, float)):
            return None if not math.isfinite(float(o)) else float(o)
        if isinstance(o, (np.bool_,)):
            return bool(o)
        if isinstance(o, (pd.Timestamp, datetime)):
            return o.isoformat()
        return o
    return json.loads(json.dumps(fix(obj), default=str))
