# Remove: import pandas as pd  ← delete this line
# Remove: import polars as pl  ← delete this line
from typing import Optional, Literal
from .flatten import flatten_records


def infer_schema_dataframe(
    records: list[dict],
    library: Literal["pandas", "polars"] = "pandas"
) -> Optional[dict]:
    if not records:
        return None

    sample = flatten_records(records[:100])

    if library == "polars":
        try:
            import polars as pl
            df = pl.DataFrame(sample)
            return dict(zip(df.columns, df.dtypes))
        except ImportError:
            return None
        except Exception:
            return None
    else:
        try:
            import pandas as pd
            df = pd.DataFrame(sample)
            return dict(zip(df.columns, df.dtypes))
        except ImportError:
            return None
        except Exception:
            return None
