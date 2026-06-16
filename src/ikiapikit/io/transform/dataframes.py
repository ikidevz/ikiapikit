from .flatten import flatten_records


def records_to_polars(records: list[dict]):
    try:
        import polars as pl
    except ImportError:
        raise ImportError("polars is required to use records_to_polars")
    return pl.DataFrame(flatten_records(records))


def records_to_pandas(records: list[dict]):
    try:
        import polars as pd
    except ImportError:
        raise ImportError("pandas  is required to use records_to_pandas")
    return pd.DataFrame(flatten_records(records))
