# Step 7 controlled infrastructure

These artifacts have not been executed. No local PostgreSQL installation is needed.
Use the dedicated managed project and Session Pooler with verified TLS.

## Mandatory managed-change stop

Before any mutation, capture the target fingerprint, PostgreSQL version, migration
revision (0001), actual ownership, existing RLS/policies and effective PUBLIC/role
grants. Have the founder review that evidence and approve execution. Stop if shared
Supabase privileges must change; do not alter managed roles, objects or schemas.

Runtime guards reject effective database CREATE/TEMP, schema CREATE and unrelated
table access, including privileges inherited through PUBLIC. PostgreSQL commonly
grants TEMP through PUBLIC: if present, the managed preflight must stop for an
explicit founder/platform decision. This artifact does not revoke shared privileges
or silently relax the no-DDL contract to make runtime startup succeed.

`runtime_roles.sql` refuses any conflicting existing role. It creates no password,
role memberships, or jous_owner. Existing administrative ownership remains. The
administrator must be able to create the private schema, assign helper ownership,
and manage policies on the four Jous tables. Never solve insufficient authority by
giving runtime privileged membership. Record any separately approved admin grants.

## Ordering

1. Complete offline tests and security review.
2. Read-only managed preflight and founder stop/review before mutations.
3. Execute the reviewed role bootstrap; inspect restricted attributes/memberships.
4. With only `JOUS_MIGRATION_DATABASE_URL` in migration tooling, upgrade to
   `0002_runtime_rls`; inspect functions, ACLs, policies and ENABLE/FORCE flags.
5. Activate a runtime password securely outside source, SQL artifacts and logs.
   Export `JOUS_DATABASE_URL` for the actual `jous_runtime` login. Do not reuse admin.
6. Run the explicitly opted-in managed validator with both separately held URLs.
7. Verify fixture cleanup, unchanged managed objects, counts and final revision.
8. Security review and separate PUBLIC CRUD SECURITY GATE. No CRUD is implemented.

The schema owner temporarily grants CREATE on the new private schema to the helper
owner solely to assign function ownership, then revokes it before migration commit.
Helper SELECT policies are role-specific and read-only. Ordinary GUCs are not a
cryptographic boundary against someone executing arbitrary SQL with runtime login.

## Validation and recovery

Use `tests/validate_managed_runtime_security.py --help` offline for options. Require
a caller-provided target fingerprint and cleanup manifest path. The fingerprint
uses host/port/database/public project reference, excluding credentials; both logins must also identify the
same server-side database. The manifest contains generated UUIDs and target metadata,
never secrets. Fixtures are administratively committed so real runtime connections
can see them. Runtime mutations roll back. Cleanup deletes only recorded rows in
Project, Membership, Organization, User order. Keep manifests until baseline checks
pass; `--cleanup-only` retries exact cleanup after an interrupted process.

Partial bootstrap requires inventory/review, not automatic role replacement.
Migration errors require revision/transaction-state inspection before retry.
Connection, ACL, ownership or recursive-policy failures keep runtime traffic blocked.
Do not disable RLS or add broad policies to make a failing test pass.

An explicitly authorized downgrade targets `0001_identity_project`, never base. It
removes Step 7 objects/grants and FORCE while retaining the required pre-existing
ENABLE RLS state. Role lifecycle and credential deactivation are separate tasks.
Unresolved fixture cleanup is a failure and needs targeted administrative recovery.
