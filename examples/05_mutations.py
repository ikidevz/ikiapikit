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

Why PATCH matters:
  PUT replaces the entire resource. PATCH sends only the fields that
  changed. Most modern APIs prefer PATCH because it is safer and more
  efficient than sending a complete replacement payload.

Uses JSONPlaceholder's fake write endpoints (they echo back the request
without actually persisting anything — perfect for demos).

Run:
    python 05_mutations.py
"""

from ikiapikit import Apikit

client = Apikit(
    base_url="https://jsonplaceholder.typicode.com",
    auth="none",
)

print("=" * 60)
print("05 · MUTATIONS — POST / PUT / PATCH / DELETE")
print("=" * 60)


# ── 1. POST — create a new resource ──────────────────────────────────────────
print("\n▶ POST /posts  — create a new post")

new_post = client.post(
    "/posts",
    body={
        "title": "apikit is amazing",
        "body": "It handles auth, pagination, and retries automatically.",
        "userId": 1,
    },
)

print("  Status  : created")
print(f"  ID      : {new_post.get('id')}")
print(f"  Title   : {new_post.get('title')}")


# ── 2. PUT — replace an existing resource ────────────────────────────────────
print("\n▶ PUT /posts/1  — replace post 1")

updated = client.put(
    "/posts/1",
    body={
        "id": 1,
        "title": "Updated title via apikit",
        "body": "Full replacement of the resource.",
        "userId": 1,
    },
)

print(f"  Updated title : {updated.get('title')}")


# ── 3. PATCH — partial update ────────────────────────────────────────────────
print("\n▶ PATCH /posts/1  — update only one field")

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
    "/posts/1",
    body={
        "id": 1,
        "title": "Full replacement via PUT",
        "body": "All fields must be included.",
        "userId": 1,
    },
)

print(f"  PUT   title  : {put_result.get('title')}")
print(f"  PUT   userId : {put_result.get('userId')}")

patch_result = client.patch(
    "/posts/1",
    body={
        "title": "Partial update via PATCH",
    },
)

print(f"  PATCH title  : {patch_result.get('title')}")
print(f"  PATCH userId : {patch_result.get('userId')}")


# ── 5. DELETE — remove a resource ────────────────────────────────────────────
print("\n▶ DELETE /posts/1  — delete post 1")

result = client.delete("/posts/1")

print(f"  Response : {result}")


# ── 6. POST with query params ────────────────────────────────────────────────
print("\n▶ POST with query params (body + params together)")

result = client.post(
    "/posts",
    body={
        "title": "test post",
        "userId": 2,
    },
    params={
        "dry_run": "true",
    },
)

print(f"  Returned ID : {result.get('id')}")


# ── 7. PATCH with query params ───────────────────────────────────────────────
print("\n▶ PATCH with query params (body + params together)")

result = client.patch(
    "/posts/1",
    body={
        "title": "Patched with dry_run flag",
    },
    params={
        "notify": "false",
        "audit": "true",
    },
)

print(f"  Result : {result.get('title')}")


# ── 8. Create → Update → Delete workflow ─────────────────────────────────────
print("\n▶ Full workflow: Create → Update → Delete")

contact = client.post(
    "/users",
    body={
        "name": "Alice Smith",
        "email": "alice@example.com",
        "phone": "555-0100",
    },
)

contact_id = contact.get("id", 11)

print(
    f"  Created  user id={contact_id} "
    f"name={contact.get('name')}"
)

updated_contact = client.put(
    f"/users/{contact_id}",
    body={
        "name": "Alice J. Smith",
        "email": "alice.j@example.com",
        "phone": "555-0100",
    },
)

print(
    f"  Updated  name={updated_contact.get('name')}"
)

client.delete(f"/users/{contact_id}")

print(f"  Deleted  user id={contact_id}")


# ── 9. PATCH workflow — CRM-style update ─────────────────────────────────────
print("\n▶ PATCH workflow — update one field without touching the rest")

contact = client.post(
    "/users",
    body={
        "name": "Maria Santos",
        "email": "maria@example.com",
        "phone": "09171234567",
        "company": "Acme PH",
    },
)

contact_id = contact.get("id", 11)

print(
    f"  Created : id={contact_id} "
    f"name={contact.get('name')}"
)

updated = client.patch(
    f"/users/{contact_id}",
    body={
        "email": "maria.santos@newdomain.com",
    },
)

print(f"  Patched : email={updated.get('email')}")
print("  Intact  : phone and company remain unchanged")


# ── 10. Batch create ─────────────────────────────────────────────────────────
print("\n▶ Batch create — 5 posts in a loop")

created_ids = []

for i in range(1, 6):
    response = client.post(
        "/posts",
        body={
            "title": f"Post #{i}",
            "userId": i,
        },
    )

    created_ids.append(response.get("id"))

print(f"  Created IDs: {created_ids}")


# ── 11. Batch PATCH ──────────────────────────────────────────────────────────
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

completed_count = sum(
    1
    for item in results
    if item.get("completed")
)

print(
    f"  Patched {len(results)} todos "
    f"— {completed_count} now completed"
)

print("\n✓ Mutations complete.\n")
