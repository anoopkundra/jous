# Step 7 runtime canary candidate procedure

This is a source-review candidate, not runtime activation approval. Migration 0002
is already committed and must not be rerun. No public traffic is admitted by the
validator. Source/security review and separate managed-canary authorization are
required before any connection or validation write.

## Independent authorities

Runtime and migration verification share `step7_execution_contract.py` and the
unchanged hash-pinned `step7_policy_template_contract.json`. Runtime verifies
post-migration relation/column, role, builtin and helper bindings separately from
policy rows, instantiates the frozen templates, then compares raw policy records.
Only opaque policy OIDs are observational; they are not template inputs.
The deployed package must include the frozen infrastructure contract artifacts at
their source-defined paths. Missing or substituted artifacts block startup.

Production requires `JOUS_ENVIRONMENT=production`, a separately held restricted
`JOUS_DATABASE_URL`, and `JOUS_DATABASE_CA_FILE` pointing to the approved public
certificate. The application constructs a pinned-only SSLContext with the reviewed
DER SHA256, CERT_REQUIRED and hostname checking. The only accepted runtime target
is the reviewed session pooler, port 5432, database postgres, and the project-qualified
runtime login. URL queries/overrides and admin identities are rejected. Migration
credentials must not be supplied to the application or validator. Auth issuer,
audience and JWKS settings must match the reviewed authentication configuration.

## Fixture prerequisite

The validator never provisions fixtures. A separate explicitly reviewed fixture
plan must pre-provision two active, non-overlapping test actors with recognized
memberships and one active project in each organization. Each actor must lack
membership in the other actor's organization. Do not use real customer identities.
No fixture provisioning is authorized by this document. If this prerequisite is
unavailable, stop rather than create rows through the validator.

Approve the exact bytes/SHA256 of a closed JSON manifest independently, before
managed observations. Its fields are:

- `schema`: `jous.runtime-canary-fixtures.v1`
- `project`: the reviewed project reference
- `issuer`: the approved authentication issuer
- `actors`: exactly two records, each with `subject`, `user`, `organization`,
  `project`; the last three are UUIDs. Corresponding identities must be distinct.

The manifest is non-secret fixture identity evidence; it must contain no tokens,
passwords or URLs bearing credentials. Its hash is an external approval input,
never calculated from a database observation and treated as approval.

## Future separately authorized invocation

Use the reviewed, isolated interpreter and installed reviewed application package:

```text
python -I -B services/api/infrastructure/validate_runtime_canary.py \
  --confirm-production-canary --production-canary \
  --fixture-manifest <approved-non-secret-manifest-path> \
  --approved-fixture-sha256 <independently-approved-64-hex-hash>
```

Do not bypass production mode by labeling the environment test/development.
The previous general managed-fixture validator is not the production procedure.

The canary validates startup security first, then same-tenant reads and rolled-back
project insert/update, cross-tenant reads/writes, missing/malformed/mismatched
context, forbidden administrative operations, physical connection reuse after
commit/rollback, and cancellation cleanup. Both success and unexpected successful
negative writes are rolled back. Savepoints isolate expected permission failures.
Only transactions containing no domain writes commit to exercise context reset.
Connection/engine cleanup occurs before sanitized PASS/FAIL reporting.

Identity-service checks use approved fixture principals; they do not prove bearer
signature/JWKS behavior. Review and test that authentication path separately before
future HTTP domain traffic. Current application routes are health-only.
Ordinary GUCs are trusted-application context, not cryptographic protection against
arbitrary SQL by someone possessing the runtime login.

## Stop and recovery

Any failure keeps public traffic blocked. Do not weaken RLS/grants or substitute
admin credentials. The validator creates no committed fixture rows and performs no
automatic repair/retry. Preserve the fixed failure report; investigate under a
separate authorization. If rollback/connection cleanup is uncertain, report failure
and do not claim successful cleanup. Pre-provisioned fixture removal, credential
revocation, deployment rollback and any further managed access need separate scope.

After source/security approval and authorized canary PASS, a separate runtime
activation decision may authorize deployment/configuration/process replacement.
Neither this document nor validator PASS switches traffic or activates runtime.

Runtime catalog checks use `SET LOCAL search_path = pg_catalog, pg_temp` inside a
rollback-only connection savepoint and verify the exact server setting before
any affected query. This includes direct policy/TEMP verification and canary
baseline checks. The savepoint is rolled back on success, failure, and
cancellation; it restores the outer transaction path and user/org GUCs without
a session-persistent change. Connection-level savepoints avoid an ORM flush.
Startup uses SQLAlchemy autobegin; scoped requests already have an explicit
outer transaction. Existing uncertain-connection disposal remains mandatory.
The restoration occurs before domain ORM queries, preserving their existing
resolution contract; this guard is specifically the security-verification
boundary, not a change to application schema configuration.

Security-query inventory: 20 distinct verification SELECTs: ROLE_CHECK,
BASELINE_CHECK, STATE_CHECK, TEMP_EVIDENCE; the four inline table/column/helper/
unrelated privilege checks in validate_runtime; and TARGET_SQL, ROLE_SQL,
TYPE_SQL, FUNCTION_SQL, OPERATOR_SQL, COLLATION_SQL, RELATION_SQL, COLUMN_SQL,
CREATED_SQL, CREATED_ACL_SQL, CREATED_SCHEMA_ACL_SQL, and POLICY_SQL from the
shared authority. All execute within the exact catalog boundary. The added
path observation is SELECT pg_catalog.current_setting('search_path'); it uses
no unqualified function, operator, cast, or relation. Startup SELECT 1, pool
pre-ping, and the canary pg_catalog.pg_backend_pid() do not depend on the path.
DatabaseContext GUC calls remain explicitly pg_catalog-qualified. SQLAlchemy
connection initialization (including default-schema discovery) is not a
security-verification authority: the frozen queries use explicit catalog/
public relation names and never consume dialect default_schema_name.

Temporary-namespace correction (offline PostgreSQL 17.11 review): explicitly
listing pg_temp after pg_catalog suppresses implicit temp-first relation/type
lookup. The pg_temp alias denotes this session's temporary namespace, not a
caller-selected schema; if none exists, there is nothing there to search.
Neither SET LOCAL nor the observation creates temporary objects. Existing temp
objects on a reused physical connection are searched after the catalog. Function
and operator lookup never searches pg_temp, so their eligible path remains only
pg_catalog. The exact configured value must be `pg_catalog, pg_temp`; reversed,
extra, omitted or hostile entries fail the observation gate. Qualified public
relations continue to bypass the search path. Savepoint rollback cancels the
local override and does not delete an earlier session temporary namespace.
Approach A avoids rewriting any frozen/shared query or expected observation.
Approach B (qualifying casts) would require eight current query definitions,
including TARGET_SQL in addition to the seven review examples, plus continued
full-surface auditing for future type references. It is unnecessary here.

Authoritative local material read (no server or network):

- C:/Program Files/PostgreSQL/17/doc/src/sgml/html/index.html identifies 17.11.
- runtime-config-client.html, search_path: SHA256
  9798f18f53084e764d56c26368536670dcf3098bd60dd7628ab19bc6351a3470.
  Establishes explicit catalog ordering, implicit temp-first ordering,
  relation/type lookup, pg_temp alias and exclusion from functions/operators.
- sql-set.html, Description: SHA256
  6b1b127bbf48ae56b17b587e72bb5cf55b9c02eaaf072b6aee645ed57a97c547.
  Establishes transaction-local duration and restoration at an earlier savepoint.
- sql-createfunction.html, Writing SECURITY DEFINER Functions Safely: SHA256
  15d8291e4336d299c8b45ff006c523cf2ff42e19b420b20e74a25e111d839424.
  Independently recommends explicit pg_temp last to avoid temporary shadowing.
- include/server/catalog/namespace.h: SearchPathMatcher separates explicit
  schemas from implicit addCatalog/addTemp; TypenameGetTypidExtended has temp_ok.

Re-audited verification definitions (Q means explicitly schema-qualified;
P means name lookup restricted by the approved path). Every row is deterministic.
Functions omitted as '-' are SQL grammar, not callable-name lookup. Ordinary
operators, IN/NOT IN and ANY comparisons use pg_catalog only; pg_temp is excluded.
All rows have no explicit COLLATE clause. Intrinsic operand collations are
catalog/column identities; target and collation metadata remain independently
verified against the frozen contract. No new collation-name lookup is introduced.

| Definition / execution site | Relations / schemas | Types/casts | Functions | Operators |
| --- | --- | --- | --- | --- |
| ROLE_CHECK | Q pg_catalog | - | Q privilege/role functions; P current_database | P comparisons, regex, IN/NOT IN |
| BASELINE_CHECK (including canary reuse) | - | - | Q current_setting | P equality |
| STATE_CHECK | Q pg_catalog, public.alembic_version | - | Q ACL/privilege functions; P count | P comparisons, IN/NOT IN, array equality |
| TEMP_EVIDENCE | Q pg_catalog | - | Q ACL/privilege/role functions; P current_database | P comparisons, regex, NOT IN |
| validate_runtime safe_tables | Inline VALUES aliases only | Q pg_catalog.name | Q has_table_privilege | P concatenation |
| validate_runtime column privileges | Q pg_catalog | Q pg_catalog.name | Q has_column_privilege | P equality, greater-than, IN |
| validate_runtime helper_safe | Q pg_catalog | - | - | P equality |
| validate_runtime unrelated_safe | Q pg_catalog | Q pg_catalog.name | Q table/column privilege functions | P comparisons, regex, IN/NOT IN |
| TARGET_SQL | Q pg_catalog | P text, integer (int4 spelling) | P current_setting/current_database | P equality |
| ROLE_SQL | Q pg_catalog | - | - | P IN equality |
| TYPE_SQL | Q pg_catalog | P text, oid | - | P equality/ANY |
| FUNCTION_SQL | Q pg_catalog | P text, oid, oid[] | - | P equality/ANY |
| OPERATOR_SQL | Q pg_catalog | P text, oid | - | P equality/ANY |
| COLLATION_SQL | Q pg_catalog | P text | - | P equality/ANY |
| RELATION_SQL | Q pg_catalog | P text | - | P equality, IN |
| COLUMN_SQL | Q pg_catalog | P text | - | P equality/ANY, greater-than |
| CREATED_SQL | Q pg_catalog | P text, oid[] | - | P equality |
| CREATED_ACL_SQL | Q pg_catalog | - | Q aclexplode/acldefault | P equality |
| CREATED_SCHEMA_ACL_SQL | Q pg_catalog | - | Q aclexplode/acldefault | P equality, inequality |
| POLICY_SQL | Q pg_catalog | Q pg_catalog.text, pg_catalog.oid[] | - | P equality, IN, array equality |

Totals: 20 security-verification definitions, all 20 resolution-sensitive and
all 20 deterministic; eight contain unqualified casts; unresolved zero. The
fully qualified path observation adds one distinct SELECT (21 including that
guard observation). The tests independently inspect actual wire SQL, distinguish
configured and effective lookup order, and replay the previous guard accepting
pg_catalog while the type audit rejects temporary text-type shadowing. These are
offline semantics/fake-catalog tests, not a managed-server canary.
