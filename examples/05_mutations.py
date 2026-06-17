"""
05_mutations.py
===============
Write operations — POST, PUT, PATCH, and DELETE.

Demonstrates:
  • client.post()     — create a resource
  • client.put()      — replace a resource
  • client.patch()    — partially update a resource
  • client.delete()   — remove a resource
  • Using params on mutations
  • PUT vs PATCH semantics
  • Chaining create → update → delete
  • Batch create / batch update workflows

Uses dummyjson.com — simulates all write operations and returns
realistic responses including isDeleted/deletedOn on DELETE.
POST uses /resource/add convention (e.g. /posts/add, /users/add).

Run:
    python 05_mutations.py
"""

from ikiapikit import Apikit

client = Apikit(
    base_url="https://dummyjson.com",
    auth="none",
)

print("=" * 60)
print("05 · MUTATIONS — POST / PUT / PATCH / DELETE")
print("=" * 60)


# ── 1. POST — create a new resource ──────────────────────────────────────────
print("\n▶ POST /posts/add  — create a new post")

new_post = client.post(
    "/posts/add",
    body={
        "title": "apikit is amazing",
        "body": "It handles auth, pagination, and retries automatically.",
        "userId": 1,
    },
)

print(f"  ID    : {new_post.get('id')}")
print(f"  Title : {new_post.get('title')}")


# ── 2. PUT — replace an existing resource ────────────────────────────────────
print("\n▶ PUT /posts/1  — replace post 1")

updated = client.put(
    "/posts/1",
    body={
        "title": "Updated title via apikit",
        "body": "Full replacement of the resource.",
        "userId": 1,
    },
)

print(f"  Updated title : {updated.get('title')}")
print(f"  userId        : {updated.get('userId')}")


# ── 3. PATCH — partial update ─────────────────────────────────────────────────
print("\n▶ PATCH /posts/1  — update only the title")

patched = client.patch(
    "/posts/1",
    body={
        "title": "Patched title — only this field changed",
    },
)

print(f"  New title : {patched.get('title')}")
print(f"  userId    : {patched.get('userId')}  ← unchanged")


# ── 4. PUT vs PATCH — semantic comparison ────────────────────────────────────
print("\n▶ PUT vs PATCH — semantic difference")

put_result = client.put(
    "/posts/2",
    body={
        "title": "Full replacement via PUT",
        "body": "All fields sent explicitly.",
        "userId": 2,
    },
)

print(f"  PUT   title  : {put_result.get('title')}")
print(f"  PUT   userId : {put_result.get('userId')}")

patch_result = client.patch(
    "/posts/2",
    body={
        "title": "Partial update via PATCH",
    },
)

print(f"  PATCH title  : {patch_result.get('title')}")
print(f"  PATCH userId : {patch_result.get('userId')}  ← untouched by PATCH")


# ── 5. DELETE — remove a resource ────────────────────────────────────────────
print("\n▶ DELETE /posts/1  — delete post 1")

result = client.delete("/posts/1")

print(f"  isDeleted : {result.get('isDeleted')}")
print(f"  deletedOn : {result.get('deletedOn')}")
print(f"  title     : {result.get('title')}")


# ── 6. POST with query params ─────────────────────────────────────────────────
print("\n▶ POST with query params (body + params together)")

result = client.post(
    "/posts/add",
    body={
        "title": "test post",
        "userId": 2,
    },
    params={
        "delay": "0",
    },
)

print(f"  Returned ID : {result.get('id')}")
print(f"  Title       : {result.get('title')}")


# ── 7. PATCH with query params ────────────────────────────────────────────────
print("\n▶ PATCH with query params (body + params together)")

result = client.patch(
    "/posts/3",
    body={
        "title": "Patched with extra query param",
    },
    params={
        "delay": "0",
    },
)

print(f"  Result : {result.get('title')}")


# ── 8. Create → Update → Delete workflow ─────────────────────────────────────
print("\n▶ Full workflow: Create → Update → Delete")

post = client.post(
    "/posts/add",
    body={
        "title": "Alice's first post",
        "body": "Hello from apikit.",
        "userId": 5,
    },
)

# dummyjson echoes a fake id on POST (nothing is persisted),
# so we use a known real id for the follow-up PUT and DELETE.
real_id = 10

print(f"  Created : id={post.get('id')} title={post.get('title')}")

updated_post = client.put(
    f"/posts/{real_id}",
    body={
        "title": "Alice's updated post",
        "body": "Full replacement via PUT.",
        "userId": 5,
    },
)
print(f"  Updated : title={updated_post.get('title')}")

deleted = client.delete(f"/posts/{real_id}")
print(
    f"  Deleted : id={deleted.get('id')} isDeleted={deleted.get('isDeleted')}")


# ── 9. PATCH workflow — partial field update ──────────────────────────────────
print("\n▶ PATCH workflow — update one field without touching the rest")

post = client.post(
    "/posts/add",
    body={
        "title": "Maria's original title",
        "body": "Original body content.",
        "userId": 8,
    },
)

print(f"  Created : id={post.get('id')} title={post.get('title')}")

patched = client.patch(
    "/posts/20",
    body={
        "title": "Maria's patched title",
    },
)

print(f"  Patched : title={patched.get('title')}")
print(f"  Intact  : body={patched.get('body')[:40]}...")


# ── 10. Batch create ──────────────────────────────────────────────────────────
print("\n▶ Batch create — 5 posts in a loop")

created_ids = []

for i in range(1, 6):
    response = client.post(
        "/posts/add",
        body={
            "title": f"Batch post #{i}",
            "body": f"This is batch post number {i}.",
            "userId": i,
        },
    )
    created_ids.append(response.get("id"))

print(f"  Created IDs : {created_ids}")


# ── 11. Batch PATCH ───────────────────────────────────────────────────────────
print("\n▶ Batch PATCH — mark 5 todos as completed")

todo_ids = [1, 2, 3, 4, 5]
results = []

for todo_id in todo_ids:
    response = client.patch(
        f"/todos/{todo_id}",
        body={
            "completed": True,
        },
    )
    results.append(response)

completed_count = sum(1 for item in results if item.get("completed"))

print(f"  Patched {len(results)} todos — {completed_count} now completed")


# ── 12. DELETE and inspect response ──────────────────────────────────────────
print("\n▶ DELETE with rich response — dummyjson returns the deleted resource")

deleted = client.delete("/products/1")

print(f"  id        : {deleted.get('id')}")
print(f"  title     : {deleted.get('title')}")
print(f"  isDeleted : {deleted.get('isDeleted')}")
print(f"  deletedOn : {deleted.get('deletedOn')}")

print("\n✓ Mutations complete.\n")
