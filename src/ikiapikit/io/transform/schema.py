import pandas as pd
import polars as pl
from typing import Optional, Literal
from .flatten import flatten_records


def infer_schema_dataframe(
    records: list[dict],
    library: Literal["pandas", "polars"] = "pandas"
) -> Optional[dict]:
    """
    Infer schema using either pandas or polars.

    Args:
        records: List of dictionaries
        library: Which library to use for inference ('pandas' or 'polars')

    Returns:
        Dictionary of {column_name: dtype} or None if records are empty
    """
    if not records:
        return None

    if library == "polars":
        if not records:
            return None

        sample = flatten_records(records[:100])

        try:
            df = pl.DataFrame(sample)
            return dict(zip(df.columns, df.dtypes))
        except Exception:
            return None
    else:
        if not records:
            return None

        sample = flatten_records(records[:100])

        try:
            df = pd.DataFrame(sample)
            return dict(zip(df.columns, df.dtypes))
        except Exception:
            return None
