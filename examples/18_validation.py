"""
18_validation.py
================
Record-level validation with Pydantic — validate & coerce on fetch.

Demonstrates:
  • fetch_records(model=MyModel)     — validate every record against a Pydantic model
  • ValidationResult                  — valid records + errors separated
  • on_invalid="skip"                — drop invalid records silently
  • on_invalid="raise"               — fail fast on first invalid record
  • on_invalid="collect"             — accumulate all errors, return both (default)
  • Type coercion                    — Pydantic fixes "123" → 123 automatically
  • Nested model validation          — models with sub-models (Address, Company)
  • strict=True                      — no coercion, exact types required
  • fetch_polars(model=...)          — validated records → Polars DataFrame
  • Validation summary report        — counts, error breakdown

Why this matters:
  APIs lie. A field documented as int arrives as string. A field marked
  required is sometimes null. Without validation these silently corrupt
  your Parquet file or crash a dbt model hours later.
  With model=MyModel, apikit validates every record at ingest time —
  you see the bad data immediately, not downstream.

Run:
    python 18_validation.py
"""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator
from iki_apikit import Apikit

print("=" * 60)
print("18 · RECORD-LEVEL PYDANTIC VALIDATION")
print("=" * 60)

BASE = "https://jsonplaceholder.typicode.com"
client = Apikit(base_url=BASE, auth="none")


# ── 1. Define models ──────────────────────────────────────────────────────────

class GeoModel(BaseModel):
    lat: float
    lng: float


class AddressModel(BaseModel):
    street: str
    suite:  Optional[str] = None
    city:   str
    zipcode: str
    geo:    Optional[GeoModel] = None


class CompanyModel(BaseModel):
    name:        str
    catchPhrase: Optional[str] = None
    bs:          Optional[str] = None


class UserModel(BaseModel):
    id:       int
    name:     str
    username: str
    email:    str          # use EmailStr if email-validator is installed
    phone:    Optional[str] = None
    website:  Optional[str] = None
    address:  Optional[AddressModel] = None
    company:  Optional[CompanyModel] = None

    @field_validator("email")
    @classmethod
    def email_must_have_at(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError(f"invalid email: {v!r}")
        return v.lower()


class PostModel(BaseModel):
    id:     int
    userId: int
    title:  str = Field(min_length=1)
    body:   str = Field(min_length=1)


class TodoModel(BaseModel):
    id:        int
    userId:    int
    title:     str
    completed: bool


# ── 2. Basic validation — model= ──────────────────────────────────────────────
print("\n▶ fetch_records('/users', model=UserModel)  — validate every record")
result = client.fetch_records(
    "/users",
    model=UserModel,
    show_progress=False,
    on_invalid="collect",   # default: accumulate errors, don't crash
)
print(f"  Total records : {result.total}")
print(f"  Valid         : {result.valid_count}")
print(f"  Invalid       : {result.error_count}")
print(f"  First valid record:")
u = result.valid[0]
print(f"    id={u.id}  name={u.name}  email={u.email}")
print(f"    city={u.address.city if u.address else 'N/A'}")


# ── 3. Access raw valid records as dicts ──────────────────────────────────────
print("\n▶ result.valid_dicts()  — list of validated + coerced dicts")
dicts = result.valid_dicts()
print(f"  Type of each item: {type(dicts[0])}")
print(f"  Sample: {dicts[0]}")


# ── 4. Type coercion ──────────────────────────────────────────────────────────
print("\n▶ Type coercion  — Pydantic fixes mismatched types automatically")


class LoosePost(BaseModel):
    id:     int    # API might return "101" (string) → coerced to 101 (int)
    userId: int
    title:  str
    body:   str


# Simulate records with string IDs (common API quirk)
bad_type_records = [
    {"id": "1", "userId": "2", "title": "Test", "body": "Content"},
    {"id": 2,   "userId": 1,   "title": "Test2", "body": "Content2"},
]
result_coerced = client._validate_records(bad_type_records, model=LoosePost)
print(f"  Record 1 id type before: {type('1').__name__}")
print(
    f"  Record 1 id type after : {type(result_coerced.valid[0].id).__name__}  ← coerced")
print(f"  All valid: {result_coerced.valid_count}/{result_coerced.total}")


# ── 5. on_invalid='skip' — drop silently ─────────────────────────────────────
print("\n▶ on_invalid='skip'  — drop invalid records, return only valid ones")


class StrictPost(BaseModel):
    id:     int
    userId: int
    title:  str = Field(min_length=50)  # unrealistically long — many will fail
    body:   str


result_skip = client.fetch_records(
    "/posts",
    params={"_limit": 10},
    model=StrictPost,
    on_invalid="skip",
    show_progress=False,
)
print(f"  Fetched 10 posts, kept {len(result_skip)} with title ≥ 50 chars")
print(f"  (returns a plain list when on_invalid='skip')")


# ── 6. on_invalid='raise' — fail fast ────────────────────────────────────────
print("\n▶ on_invalid='raise'  — raise ValidationError on first bad record")


class RequireEmail(BaseModel):
    id:    int
    email: str = Field(pattern=r"^[^@]+@[^@]+\.[^@]+$")


try:
    # /comments has some oddly formatted emails in the fixture — may trigger
    result_raise = client.fetch_records(
        "/comments",
        params={"_limit": 5},
        model=RequireEmail,
        on_invalid="raise",
        show_progress=False,
    )
    print(
        f"  All {len(result_raise)} records valid (JSONPlaceholder emails are well-formed)")
except Exception as e:
    print(f"  Caught: {type(e).__name__}: {str(e)[:80]}")


# ── 7. Error inspection ───────────────────────────────────────────────────────
print("\n▶ result.errors  — inspect what went wrong")

# Inject some bad records manually
mixed_records = [
    {"id": 1,   "userId": 1, "title": "Good post",  "body": "Content here."},
    {"id": "x", "userId": 1, "title": "Bad id",     "body": "Content here."},  # bad
    {"id": 3,   "userId": 1, "title": "",
        "body": "Content here."},  # bad
    {"id": 4,   "userId": 1, "title": "Also good",  "body": "Content here."},
]
result_err = client._validate_records(mixed_records, model=PostModel)

print(f"  Valid   : {result_err.valid_count}")
print(f"  Errors  : {result_err.error_count}")
for err in result_err.errors:
    print(f"    record_index={err['index']}  "
          f"field={err.get('field', '?')}  "
          f"msg={err['message'][:60]}")


# ── 8. Validation summary ─────────────────────────────────────────────────────
print("\n▶ result.summary()  — human-readable report")
result_full = client.fetch_records(
    "/todos",
    model=TodoModel,
    show_progress=False,
    on_invalid="collect",
)
result_full.summary()   # prints a Rich table


# ── 9. fetch_polars(model=...) ────────────────────────────────────────────────
print("\n▶ fetch_polars(model=TodoModel)  — validated records → Polars DataFrame")
try:
    import polars as pl
    df = client.fetch_polars(
        "/todos",
        params={"_limit": 20},
        model=TodoModel,
        show_progress=False,
    )
    print(f"  Shape   : {df.shape}")
    print(f"  Schema  : {df.schema}")
    print(f"  completed rate: {df['completed'].mean()*100:.0f}%")
except ImportError:
    print("  (polars not installed)")


# ── 10. strict=True — no coercion ────────────────────────────────────────────
print("\n▶ strict=True  — exact types required, no coercion")
print("""
  result = client.fetch_records(
      "/posts",
      model=PostModel,
      strict=True,   # "101" (str) will NOT be coerced to 101 (int) — error instead
      on_invalid="collect",
  )
  # Use when you need to catch upstream type drift explicitly,
  # rather than silently fix it.
""")


# ── 11. Nested model validation ───────────────────────────────────────────────
print("\n▶ Nested models  — address.city + company.name validated recursively")
result_nested = client.fetch_records(
    "/users",
    model=UserModel,
    show_progress=False,
    on_invalid="collect",
)
valid_user = result_nested.valid[0]
print(f"  user.name          : {valid_user.name}")
print(
    f"  user.address.city  : {valid_user.address.city if valid_user.address else 'N/A'}")
print(
    f"  user.address.geo   : lat={valid_user.address.geo.lat if valid_user.address and valid_user.address.geo else 'N/A'}")
print(
    f"  user.company.name  : {valid_user.company.name if valid_user.company else 'N/A'}")

print("\n✓ Pydantic validation complete.\n")
