"""
19_hooks.py
===========
Pluggable alerting hooks — fire callbacks on errors, 429s, and more.

Demonstrates:
  • on_error=fn        — called whenever a request raises an exception
  • on_rate_limit=fn   — called on every 429 response
  • on_retry=fn        — called before each retry attempt
  • on_response=fn     — called after every successful response (middleware)
  • on_page=fn         — called after each page in a paginated fetch
  • HookContext         — rich object passed to every hook (url, status, etc.)
  • Async hooks        — async def hooks work alongside sync ones
  • Built-in hooks     — SlackHook, LogHook, PagerDutyHook (pre-wired)
  • HookChain          — combine multiple hooks into one
  • Removing hooks     — client.hooks.clear() / client.hooks.remove(fn)

Real-world use cases:
  • Post to a Slack channel when an API starts returning 5xx
  • Page on-call (PagerDuty) when rate limits are hit in production
  • Log every response to a structured logger for audit trails
  • Emit metrics to Prometheus / Datadog on each page fetched
  • Email a digest when a nightly fetch produces validation errors

Run:
    python 19_hooks.py
"""

from ikiapikit import HookChain
import logging
import time
from ikiapikit import (
    Apikit, ApiConfig, AuthConfig, PaginationConfig,
    HookContext, LogHook,
)

print("=" * 60)
print("19 · ALERTING HOOKS")
print("=" * 60)

BASE = "https://jsonplaceholder.typicode.com"
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


# ── 1. on_error — simple print hook ──────────────────────────────────────────
print("\n▶ on_error  — called whenever a request raises an exception")

errors_seen = []


def my_error_hook(ctx: HookContext) -> None:
    errors_seen.append(ctx)
    print(
        f"  [HOOK] Error on {ctx.url}: {ctx.error_type} — {ctx.error_message}")


client = Apikit(
    base_url=BASE,
    auth="none",
    on_error=my_error_hook,
)

try:
    client.fetch_records("/this-does-not-exist", show_progress=False)
except Exception:
    pass

if errors_seen:
    print(f"  Hook fired {len(errors_seen)} time(s)")
    print(
        f"  Context: url={errors_seen[0].url}  status={errors_seen[0].status_code}")
else:
    print(f"  Hook registered — fires on errors during fetch.")


# ── 2. on_rate_limit — called on 429 ─────────────────────────────────────────
print("\n▶ on_rate_limit  — called on every 429 response")

rate_limit_events = []


def my_rate_limit_hook(ctx: HookContext) -> None:
    rate_limit_events.append(ctx)
    retry_after = ctx.headers.get("Retry-After", "unknown")
    print(f"  [HOOK] 429 on {ctx.url}  retry_after={retry_after}s")
    # In production: alert #ops-alerts Slack channel, throttle all workers, etc.


client_rl = Apikit(
    base_url=BASE,
    auth="none",
    on_rate_limit=my_rate_limit_hook,
)
# JSONPlaceholder won't 429, so show the pattern with config:
print(f"  Hook registered. Will fire automatically on any 429 response.")
print(f"  apikit still auto-retries after calling the hook.")


# ── 3. on_retry — visibility into retry loop ──────────────────────────────────
print("\n▶ on_retry  — called before each retry attempt")

retry_log = []


def my_retry_hook(ctx: HookContext) -> None:
    retry_log.append(ctx)
    print(f"  [HOOK] Retry #{ctx.attempt} for {ctx.url}  "
          f"(waiting {ctx.wait_seconds:.1f}s, reason={ctx.error_type})")


client_retry = Apikit(
    base_url="https://httpbin.org",
    auth="none",
    on_retry=my_retry_hook,
)
print(f"  on_retry hook registered. Fires before each backoff sleep.")
print(f"  ctx.attempt tells you which retry you're on (1-based).")
print(f"  ctx.wait_seconds tells you how long apikit will sleep.")


# ── 4. on_response — middleware / audit trail ─────────────────────────────────
print("\n▶ on_response  — called after every successful response")

response_log = []


def audit_hook(ctx: HookContext) -> None:
    response_log.append({
        "ts":      time.time(),
        "url":     ctx.url,
        "status":  ctx.status_code,
        "latency": ctx.latency_ms,
        "records": ctx.record_count,
    })


client_audit = Apikit(base_url=BASE, auth="none", on_response=audit_hook)
client_audit.fetch_records("/posts/1", show_progress=False)
client_audit.fetch_records("/users/1", show_progress=False)

print(f"  Audit log has {len(response_log)} entries:")
for entry in response_log:
    print(f"    {entry['url']:<45}  "
          f"status={entry['status']}  "
          f"latency={entry['latency']:.0f}ms")


# ── 5. on_page — per-page callback during pagination ─────────────────────────
print("\n▶ on_page  — called after each page in a paginated fetch")

page_log = []


def page_hook(ctx: HookContext) -> None:
    page_log.append(ctx)
    print(f"  [HOOK] Page {ctx.page_number}: "
          f"{ctx.record_count} records, "
          f"cumulative={ctx.cumulative_records}")


cfg = ApiConfig(
    base_url=BASE,
    auth=AuthConfig(type="none"),
    pagination=PaginationConfig(
        strategy="offset",
        page_size=10,
        limit_param="_limit",
        offset_param="_start",
        max_pages=3,
    ),
)
paged_client = Apikit.from_config(cfg, on_page=page_hook)
records = paged_client.fetch_records(
    "/posts", paginate=True, show_progress=False)
print(f"\n  Fetched {len(records)} records across {len(page_log)} pages")


# ── 6. HookChain — combine multiple hooks ─────────────────────────────────────
print("\n▶ HookChain  — run several hooks in sequence")


def slack_alerter(ctx: HookContext) -> None:
    print(f"  [SLACK]  Would post: 'Error on {ctx.url}: {ctx.error_type}'")


def pagerduty_alerter(ctx: HookContext) -> None:
    print(f"  [PAGER]  Would create incident for {ctx.url}")


def metrics_counter(ctx: HookContext) -> None:
    print(f"  [METRIC] error_count++  labels={{url={ctx.url!r}}}")


chain = HookChain(on_error=[slack_alerter, pagerduty_alerter, metrics_counter])

client_chain = Apikit(base_url=BASE, auth="none", on_error=chain)
try:
    client_chain.fetch_records("/does-not-exist", show_progress=False)
except Exception:
    pass
print(f"  All 3 hooks in the chain fired in order ↑")


# ── 7. Built-in LogHook ───────────────────────────────────────────────────────
print("\n▶ LogHook  — structured logging for every response")

log_hook = LogHook(
    logger=logging.getLogger("apikit.demo"),
    level=logging.INFO,
    include_headers=False,   # set True for full header audit
)

client_log = Apikit(base_url=BASE, auth="none", on_response=log_hook)
client_log.fetch_records("/users/1", show_progress=False)
print(f"  (LogHook writes to Python logging — see INFO line above)")


# ── 8. Built-in SlackHook ─────────────────────────────────────────────────────
print("\n▶ SlackHook  — post to Slack on errors")
print("""
  from ikiapikit import SlackHook

  slack = SlackHook(
      webhook_url=os.environ["SLACK_WEBHOOK_URL"],
      channel="#ops-alerts",
      mention="@oncall",
      min_status=500,      # only alert on 5xx, not 4xx
  )

  client = Apikit(
      base_url="https://api.production.com",
      auth="bearer",
      token=os.environ["API_TOKEN"],
      on_error=slack,
      on_rate_limit=slack,
  )

  # Now any 5xx or 429 automatically posts to #ops-alerts.
""")


# ── 9. Async hooks ────────────────────────────────────────────────────────────
print("\n▶ Async hooks  — async def hooks work seamlessly")
print("""
  import asyncio
  from ikiapikit import Apikit, HookContext

  async def async_alert(ctx: HookContext) -> None:
      async with httpx.AsyncClient() as hc:
          await hc.post(
              "https://hooks.slack.com/services/...",
              json={"text": f"Error: {ctx.url} returned {ctx.status_code}"},
          )

  client = Apikit(
      base_url="https://api.example.com",
      auth="bearer",
      token="...",
      on_error=async_alert,   # async hooks accepted wherever sync hooks are
  )

  async def main():
      await client.afetch_records("/events", paginate=True)

  asyncio.run(main())
""")


# ── 10. HookContext fields reference ─────────────────────────────────────────
print("\n▶ HookContext — all available fields")
print("""
  ctx.url             — full URL of the request
  ctx.method          — "GET", "POST", "PATCH", etc.
  ctx.status_code     — HTTP status (0 if no response, e.g. network error)
  ctx.latency_ms      — round-trip time in milliseconds
  ctx.headers         — response headers dict
  ctx.record_count    — records in this response (0 for errors)
  ctx.page_number     — current page (on_page hook only)
  ctx.cumulative_records — total records so far (on_page hook only)
  ctx.attempt         — retry attempt number (on_retry hook only, 1-based)
  ctx.wait_seconds    — planned backoff sleep (on_retry hook only)
  ctx.error_type      — exception class name (on_error / on_retry)
  ctx.error_message   — exception message (on_error / on_retry)
  ctx.error           — original exception object (on_error / on_retry)
""")


# ── 11. Remove / clear hooks ──────────────────────────────────────────────────
print("\n▶ Removing hooks at runtime")
print("""
  # Remove a specific hook
  client.hooks.remove(my_error_hook, event="on_error")

  # Clear all hooks for one event
  client.hooks.clear(event="on_error")

  # Clear every hook on the client
  client.hooks.clear_all()
""")

print("\n✓ Hooks & alerting complete.\n")
