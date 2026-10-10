"""Shared, data-only Step 7 catalog contract. No database or settings access."""
import re

USER_NAMESPACE = """n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
 AND n.nspname !~ '^pg_(temp|toast_temp)_[0-9]+$'"""

_POLICY_PROJECTION = """SELECT p.oid AS policy_oid,c.oid AS relation_oid,
 n.nspname AS namespace,c.relname AS relation_name,p.polname AS policy_name,
 p.polcmd::pg_catalog.text AS command,p.polpermissive AS permissive,
 p.polroles::pg_catalog.oid[] AS role_oids,
 p.polqual::pg_catalog.text AS using_tree,
 p.polwithcheck::pg_catalog.text AS check_tree,c.relowner AS owner_oid,
 p.polroles=ARRAY[(SELECT r.oid FROM pg_catalog.pg_roles r WHERE r.rolname=
   CASE WHEN p.polname IN ('jous_users_helper_read','jous_organizations_helper_read')
     THEN 'jous_security_reader' ELSE 'jous_runtime' END)] AS role_contract
 FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
"""
ALL_POLICY_SQL = _POLICY_PROJECTION + ' ORDER BY c.oid,p.oid'
POLICY_SQL = _POLICY_PROJECTION + """ WHERE n.nspname='public'
 AND c.relname IN ('users','organizations','organization_memberships','projects')
 ORDER BY c.oid,p.oid"""

# Historical concrete-record API sentinel, retained for offline evidence tests.
# Production migration AND runtime use step7_execution_contract's hash-pinned
# templates and independent bindings instead. Never populate this from live rows.
APPROVED_POLICY_CONTRACT = None


def user_namespace(name):
    return (type(name) is str and name not in
            ('pg_catalog', 'information_schema', 'pg_toast') and
            re.fullmatch(r'pg_(temp|toast_temp)_[0-9]+', name) is None)


def default_count(value, input_count):
    return type(value) is int and type(input_count) is int and 0 <= value <= input_count


def policy_record(record):
    fields = {'policy_oid', 'relation_oid', 'namespace', 'relation_name',
              'policy_name', 'command', 'permissive', 'role_oids',
              'using_tree', 'check_tree', 'owner_oid', 'role_contract'}
    oid = lambda value: type(value) is int and 0 < value <= 4294967295
    return (type(record) is dict and set(record) == fields and
            all(oid(record[key]) for key in ('policy_oid', 'relation_oid', 'owner_oid')) and
            type(record['namespace']) is str and record['namespace'] == 'public' and
            type(record['relation_name']) is str and
            record['relation_name'] in ('users','organizations','organization_memberships','projects') and
            type(record['policy_name']) is str and bool(record['policy_name']) and
            type(record['command']) is str and record['command'] in ('*','r','a','w','d') and
            type(record['permissive']) is bool and
            record['role_contract'] is True and
            type(record['role_oids']) is list and len(record['role_oids']) == 1 and
            all(oid(value) for value in record['role_oids']) and
            len(record['role_oids']) == len(set(record['role_oids'])) and
            all(record[key] is None or (type(record[key]) is str and bool(record[key]))
                for key in ('using_tree', 'check_tree')))


def verify_policy_records(records, expected):
    """Opaque exact comparison: never parse, normalize or evaluate a tree."""
    if type(records) is not list or type(expected) is not list or len(expected) != 13:
        raise ValueError('POLICY_EVIDENCE_UNRESOLVED')
    # Preserve the migration-owned names, command, mode, role and NULL contract
    # independently of whatever future raw evidence is proposed for approval.
    metadata = {}
    commands = {'users': ('r',), 'organization_memberships': ('r',),
                'organizations': ('r','w'), 'projects': ('r','a','w')}
    suffix = {'r':'select','a':'insert','w':'update'}
    for table, actions in commands.items():
        metadata[(table, f'jous_{table}_guard')] = ('*', False, True, True)
        for action in actions:
            metadata[(table, f'jous_{table}_{suffix[action]}')] = (
                action, True, action != 'a', action in ('a','w'))
        if table in ('users','organizations'):
            metadata[(table, f'jous_{table}_helper_read')] = ('r', True, True, False)
    for collection in (records, expected):
        if not all(policy_record(record) for record in collection):
            raise ValueError('POLICY_STRUCTURAL_VALUE')
        if (len(collection) != len(metadata) or
            {(r['relation_name'],r['policy_name']) for r in collection} != set(metadata)):
            raise ValueError('POLICY_SET')
        for record in collection:
            actual = (record['command'],record['permissive'],
                      record['using_tree'] is not None,record['check_tree'] is not None)
            if actual != metadata[(record['relation_name'],record['policy_name'])]:
                raise ValueError('POLICY_METADATA')
        if (len({r['policy_oid'] for r in collection}) != len(collection) or
            len({(r['relation_oid'], r['policy_name']) for r in collection}) != len(collection)):
            raise ValueError('POLICY_DUPLICATE')
    key = lambda r: (r['relation_oid'], r['policy_oid'])
    if sorted(records, key=key) != sorted(expected, key=key):
        raise ValueError('POLICY_STRUCTURAL_MISMATCH')
