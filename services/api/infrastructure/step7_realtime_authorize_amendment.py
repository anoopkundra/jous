"""One reviewed inventory supplement; SELECT-only collection, no execution approval.

This does not replace the executable manifest parser or its unresolved M1/policy
gates. Production requires the full supplemental snapshot and exact 97 inventory.
No connections, credential access, routine invocation, or live-state learning.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / 'services/api/infrastructure/step7_realtime_authorize_amendment.json'
SHA256 = 'ad494861a54cb78afa1235fa661a046e2ed182605b7bb6295579968be22497f3'
BASE_SHA256 = '60efef97d11e85a0be679a32f5aa3163f35017f4bebf8d6120bdb183731734e0'
BODY_SHA256 = '501bab2fb4e2d0a183a9cbb3c5702d0d2a8120e2bdaa1c4ba4a7eb531b6138fa'
IDENTITY = ('realtime', 'authorize', 'f',
            tuple([('pg_catalog', 'text')] * 5 + [('pg_catalog', '_text')] * 2))
MULTISETS = frozenset(('dependencies', 'dependency_bindings', 'routine_acl_effective',
    'schema_acl_effective', 'reachability', 'membership_paths', 'type_bindings',
    'identity_candidates'))


class AmendmentRejected(ValueError):
    pass


def require(condition, gate):
    if not condition:
        raise AmendmentRejected(gate)


def canonical(value):
    # Type-sensitive JSON distinguishes true/1 and false/0. Reject arbitrary data.
    def check(item):
        require(item is None or type(item) in (str, int, bool, list, dict), 'AMENDMENT_TYPE')
        if type(item) is list:
            for child in item: check(child)
        if type(item) is dict:
            require(all(type(k) is str for k in item), 'AMENDMENT_KEY_TYPE')
            for child in item.values(): check(child)
    check(value)
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def parse(payload):
    def pairs(entries):
        result = {}
        for key, value in entries:
            require(key not in result, 'AMENDMENT_DUPLICATE_KEY')
            result[key] = value
        return result
    require(type(payload) is bytes and len(payload) <= 1000000, 'AMENDMENT_SIZE')
    value = json.loads(payload, object_pairs_hook=pairs)
    canonical(value)
    return value


def load_amendment():
    require(PATH.is_file() and not PATH.is_symlink(), 'AMENDMENT_PATH')
    payload = PATH.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == SHA256, 'AMENDMENT_HASH')
    amendment = parse(payload)
    require(amendment['base_manifest_sha256'] == BASE_SHA256 and
        amendment['targeted_evidence_sha256'] ==
        '9dc1911c466a4f9d7d22dcc936158ee23aa45b6322f49dbcf07fc8ada7e5bcca' and
        amendment['parent_evidence_sha256'] ==
        '922b335f605d9f96b14791bdb2d4896d2c55f43e7ad0f0116417c54a2826ee79', 'AMENDMENT_LINKAGE')
    require(all(amendment[k] is False for k in ('execution_approved',
        'migration_execution_approved', 'runtime_activation_approved')), 'AMENDMENT_APPROVAL')
    source = amendment['targeted_contract']['core'][0]['prosrc']
    require(type(source) is str and hashlib.sha256(source.encode('utf-8')).hexdigest()
            == BODY_SHA256, 'AMENDMENT_BODY_HASH')
    return amendment


def verify_targeted_snapshot(observed):
    """Require the complete closed supplemental projection, not selected counts.

    Order is immaterial only for catalog multisets. Duplicates are retained and
    rejected when multiplicity differs. Argument arrays/body/NULL remain exact.
    Missing, extra, unknown, relaxed, and incorrectly typed observations fail.
    The caller must supply current independently collected primitive observations.
    """
    expected = load_amendment()['targeted_contract']
    require(type(observed) is dict and set(observed) == set(expected), 'AUTHORIZE_SNAPSHOT_KEYS')
    for key in sorted(expected):
        if key in MULTISETS:
            require(type(observed[key]) is list, 'AUTHORIZE_' + key.upper())
            actual = sorted(canonical(x) for x in observed[key])
            wanted = sorted(canonical(x) for x in expected[key])
        else:
            actual, wanted = canonical(observed[key]), canonical(expected[key])
        require(actual == wanted, 'AUTHORIZE_' + key.upper())
    return True


def routine_entry():
    """Project exact approved evidence into the existing inventory schema."""
    contract = load_amendment()['targeted_contract']
    core = contract['core'][0]
    types = {x['oid']: {'schema': x['nspname'], 'name': x['typname']}
             for x in contract['type_bindings']}
    attributes = ('rolsuper', 'rolbypassrls', 'rolcreatedb', 'rolcreaterole',
                  'rolreplication', 'rolinherit', 'rolcanlogin')
    return dict(schema=core['namespace'], name=core['proname'], routine_kind=core['prokind'],
        identity_input_types=[types[x] for x in core['proargtypes']],
        return_type=types[core['prorettype']], returns_set=core['proretset'],
        parameter_names=core['proargnames'], parameter_modes=core['proargmodes'],
        all_argument_types=[types[x] for x in core['proallargtypes']],
        default_argument_count=core['pronargdefaults'], variadic_type=None,
        owner=core['owner'], owner_attributes={k: core[k] for k in attributes},
        language=core['lanname'], security_definer=core['prosecdef'],
        volatility=core['provolatile'], parallel=core['proparallel'], strict=core['proisstrict'],
        leakproof=core['proleakproof'], proconfig=core['proconfig'],
        public_acl=[dict(grantor=x['grantor_name'], grantee='PUBLIC',
            privilege=x['privilege_type'], grant_option=x['is_grantable'])
            for x in contract['routine_acl_effective'] if x['grantee'] == 0],
        direct_jous_grants=[], extension_membership=None,
        schema_usage={x['rolname']: x['schema_usage'] for x in contract['reachability']},
        execution_context='ordinary_function', parsed_sql_body=core['prosqlbody'] is not None,
        source=core['prosrc'], source_sha256=BODY_SHA256,
        fingerprint_algorithm='SHA256_UTF8_PROSRC_EXACT')


def build_candidate(base_bytes):
    """Compose only in memory; never an approved execution manifest."""
    require(type(base_bytes) is bytes and hashlib.sha256(base_bytes).hexdigest()
            == BASE_SHA256, 'AMENDMENT_BASE_HASH')
    inventory = parse(base_bytes)
    require(len(inventory['routines']) == 96, 'AMENDMENT_BASE_COUNT')
    inventory['routines'].append(routine_entry())
    inventory['routines'].sort(key=lambda x: canonical([x['schema'], x['name'],
                                                       x['identity_input_types']]))
    amendment = load_amendment()
    return dict(status='OFFLINE_REVIEWED_ROUTINE_AMENDMENT_CANDIDATE',
        execution_approved=False, migration_execution_approved=False,
        runtime_activation_approved=False, post_0002_raw_policy_contract=None,
        base_manifest_sha256=BASE_SHA256,
        targeted_evidence_sha256=amendment['targeted_evidence_sha256'],
        parent_evidence_sha256=amendment['parent_evidence_sha256'],
        inventory_contract=inventory)


def verify_reviewed_inventory(actual_inventory, targeted_snapshot, runner):
    """Offline candidate verification using the private production comparator.

    Never call the original 96-row comparison separately to approve this candidate:
    both exact 97-row inventory and full supplemental constraints are mandatory.
    This helper does not authorize execution. The production entry point is
    runner.verify_public_compatibility, which collects current supplemental rows.
    """
    verify_targeted_snapshot(targeted_snapshot)
    candidate = build_candidate((ROOT / runner.MANIFEST_PATH).read_bytes())
    runner._compare_public_inventory(actual_inventory, candidate['inventory_contract'])
    return candidate


# Exact reviewed SELECT projections retained from the approved targeted session.
PROJECTIONS = {'identity_candidates': ("SELECT p.oid,p.pronamespace,n.nspname,p.prokind::pg_catalog.text AS prokind,p.proargtypes::pg_catalog.oid[] AS input_oids,\n    ARRAY(SELECT tn.nspname::pg_catalog.text FROM pg_catalog.unnest(p.proargtypes::pg_catalog.oid[]) WITH ORDINALITY a(oid,pos) JOIN pg_catalog.pg_type t ON t.oid=a.oid JOIN pg_catalog.pg_namespace tn ON tn.oid=t.typnamespace ORDER BY a.pos) AS input_namespaces,\n    ARRAY(SELECT t.typname::pg_catalog.text FROM pg_catalog.unnest(p.proargtypes::pg_catalog.oid[]) WITH ORDINALITY a(oid,pos) JOIN pg_catalog.pg_type t ON t.oid=a.oid ORDER BY a.pos) AS input_names\n    FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='realtime' AND p.proname='authorize' AND p.prokind='f' ORDER BY p.oid", {}), 'core': ('SELECT p.oid,p.pronamespace,n.nspname AS namespace,p.proname,p.proowner,o.rolname AS owner,o.rolcanlogin,o.rolsuper,o.rolbypassrls,o.rolcreatedb,o.rolcreaterole,o.rolreplication,o.rolinherit,o.rolconnlimit,p.prolang,l.lanname,p.prokind::pg_catalog.text AS prokind,p.prosecdef,p.provolatile::pg_catalog.text AS provolatile,p.proparallel::pg_catalog.text AS proparallel,p.proisstrict,p.proleakproof,p.proretset,p.prorettype,rt.typname AS return_type,rn.nspname AS return_namespace,p.proargtypes::pg_catalog.oid[] AS proargtypes,p.proallargtypes,p.proargmodes::pg_catalog.text[] AS proargmodes,p.proargnames,p.pronargdefaults,p.provariadic,p.proconfig,p.probin,p.prosrc,p.prosqlbody::pg_catalog.text AS prosqlbody\n    FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace JOIN pg_catalog.pg_roles o ON o.oid=p.proowner JOIN pg_catalog.pg_language l ON l.oid=p.prolang JOIN pg_catalog.pg_type rt ON rt.oid=p.prorettype JOIN pg_catalog.pg_namespace rn ON rn.oid=rt.typnamespace WHERE p.oid=:oid', {'oid': 17784}), 'type_bindings': ('SELECT t.oid,t.typnamespace,n.nspname,t.typname,t.typtype::pg_catalog.text AS typtype,t.typelem FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace WHERE t.oid=ANY(CAST(:ids AS pg_catalog.oid[])) ORDER BY t.oid', {'ids': [25, 1000, 1009, 2249]}), 'routine_acl_raw': ("SELECT p.proacl IS NULL AS proacl_is_null,p.proacl::pg_catalog.text AS raw_proacl,pg_catalog.acldefault('f',p.proowner)::pg_catalog.text AS default_acl FROM pg_catalog.pg_proc p WHERE p.oid=:oid", {'oid': 17784}), 'routine_acl_effective': ("SELECT a.grantor,g.rolname AS grantor_name,a.grantee,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE u.rolname::pg_catalog.text END AS grantee_name,a.privilege_type,a.is_grantable FROM pg_catalog.pg_proc p CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a LEFT JOIN pg_catalog.pg_roles g ON g.oid=a.grantor LEFT JOIN pg_catalog.pg_roles u ON u.oid=a.grantee WHERE p.oid=:oid ORDER BY a.grantee,a.grantor,a.privilege_type,a.is_grantable", {'oid': 17784}), 'schema_acl_raw': ("SELECT n.oid,n.nspname,n.nspowner,o.rolname AS owner,n.nspacl IS NULL AS acl_is_null,n.nspacl::pg_catalog.text AS raw_acl,pg_catalog.acldefault('n',n.nspowner)::pg_catalog.text AS default_acl FROM pg_catalog.pg_namespace n JOIN pg_catalog.pg_roles o ON o.oid=n.nspowner WHERE n.oid=:oid", {'oid': 16559}), 'schema_acl_effective': ("SELECT a.grantor,g.rolname AS grantor_name,a.grantee,CASE WHEN a.grantee=0 THEN 'PUBLIC' ELSE u.rolname::pg_catalog.text END AS grantee_name,a.privilege_type,a.is_grantable FROM pg_catalog.pg_namespace n CROSS JOIN LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a LEFT JOIN pg_catalog.pg_roles g ON g.oid=a.grantor LEFT JOIN pg_catalog.pg_roles u ON u.oid=a.grantee WHERE n.oid=:oid ORDER BY a.grantee,a.grantor,a.privilege_type,a.is_grantable", {'oid': 16559}), 'reachability': ("SELECT r.oid,r.rolname,r.rolcanlogin,r.rolsuper,r.rolbypassrls,r.rolcreatedb,r.rolcreaterole,r.rolreplication,r.rolinherit,pg_catalog.has_schema_privilege(r.oid,'realtime','USAGE') AS schema_usage,pg_catalog.has_function_privilege(r.oid,CAST(:oid AS pg_catalog.oid),'EXECUTE') AS routine_execute,pg_catalog.pg_has_role(r.oid,CAST(:role AS pg_catalog.oid),'MEMBER') AS owner_member,pg_catalog.pg_has_role(r.oid,CAST(:role AS pg_catalog.oid),'SET') AS owner_set,pg_catalog.pg_has_role(r.oid,CAST(:role AS pg_catalog.oid),'USAGE') AS owner_inherited FROM pg_catalog.pg_roles r WHERE r.rolname IN ('jous_runtime','jous_security_reader') ORDER BY r.rolname", {'oid': 17784, 'role': 17270}), 'membership_paths': ("SELECT m.roleid,m.member,m.grantor,r.rolname AS role_name,u.rolname AS member_name,g.rolname AS grantor_name,m.admin_option,m.inherit_option,m.set_option FROM pg_catalog.pg_auth_members m JOIN pg_catalog.pg_roles r ON r.oid=m.roleid JOIN pg_catalog.pg_roles u ON u.oid=m.member JOIN pg_catalog.pg_roles g ON g.oid=m.grantor WHERE m.member IN (WITH RECURSIVE reachable(oid) AS (SELECT oid FROM pg_catalog.pg_roles WHERE rolname IN ('jous_runtime','jous_security_reader') UNION SELECT a.roleid FROM pg_catalog.pg_auth_members a JOIN reachable x ON x.oid=a.member) SELECT oid FROM reachable) OR m.roleid=:role ORDER BY m.member,m.roleid,m.grantor", {'role': 17270}), 'dependencies': ("SELECT d.classid,d.objid,d.objsubid,d.refclassid,d.refobjid,d.refobjsubid,d.deptype::pg_catalog.text AS deptype,cn.nspname AS destination_class_namespace,cc.relname AS destination_class FROM pg_catalog.pg_depend d LEFT JOIN pg_catalog.pg_class cc ON cc.oid=d.refclassid LEFT JOIN pg_catalog.pg_namespace cn ON cn.oid=cc.relnamespace WHERE d.classid=(SELECT c.oid FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='pg_catalog' AND c.relname='pg_proc') AND d.objid=:oid ORDER BY d.objsubid,d.refclassid,d.refobjid,d.refobjsubid,d.deptype", {'oid': 17784}), 'language_binding': ('SELECT oid,lanname,lanowner,lanispl,lanpltrusted,lanplcallfoid,laninline,lanvalidator FROM pg_catalog.pg_language WHERE oid=:oid', {'oid': 13619}), 'namespace_binding': ('SELECT oid,nspname,nspowner FROM pg_catalog.pg_namespace WHERE oid=:oid', {'oid': 16559})}


def collect_snapshot(connection, rows):
    """Bounded production catalog collection; no routine invocation or mutation."""
    expected = load_amendment()['targeted_contract']
    observed = {}
    for key in ('identity_candidates', 'core', 'type_bindings', 'routine_acl_raw',
                'routine_acl_effective', 'schema_acl_raw', 'schema_acl_effective',
                'reachability', 'membership_paths', 'dependencies'):
        sql, parameters = PROJECTIONS[key]
        observed[key] = rows(connection, sql, parameters)
        # Reject unexpected identities before following the pinned numeric targets.
        if key in ('identity_candidates', 'core', 'dependencies'):
            require(canonical(observed[key]) == canonical(expected[key]),
                    'AUTHORIZE_' + key.upper())
    observed['resolved_identity'] = observed['identity_candidates'][0]
    source = observed['core'][0]['prosrc']
    observed['prosrc_sha256_utf8_exact'] = hashlib.sha256(source.encode('utf-8')).hexdigest()
    observed['previous_prosrc_hash_match'] = observed['prosrc_sha256_utf8_exact'] == BODY_SHA256
    observed['public_execute_provenance'] = ('DEFAULT_ACL' if
        observed['routine_acl_raw'][0]['proacl_is_null'] else 'EXPLICIT_PROACL')
    observed['dependency_bindings'] = []
    for edge, key in zip(observed['dependencies'], ('language_binding', 'namespace_binding')):
        sql, parameters = PROJECTIONS[key]
        bindings = rows(connection, sql, parameters)
        observed['dependency_bindings'].append(dict(refclassid=edge['refclassid'],
            refobjid=edge['refobjid'], refobjsubid=edge['refobjsubid'],
            status='RESOLVED' if len(bindings) == 1 else 'UNRESOLVED', rows=bindings))
    verify_targeted_snapshot(observed)
    return observed
