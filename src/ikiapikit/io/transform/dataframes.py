import pandas as pd
import polars as pl
from .flatten import flatten_records


def records_to_polars(records: list[dict]) -> "pl.DataFrame":
    """Convert a list of records to a Polars DataFrame with automatic nested-JSON flattening."""
    flat = flatten_records(records)
    return pl.DataFrame(flat)


def records_to_pandas(records: list[dict]) -> "pd.DataFrame":
    """Convert a list of records to a Pandas DataFrame with automatic nested-JSON flattening."""
    flat = flatten_records(records)
    return pd.DataFrame(flat)
