"""Offline/data-only retention boundary for a separately authorized collector.

This module neither connects nor reads credentials nor writes artifacts. The
caller owns TLS/target/read-only verification and connection rollback/closure.
An EvidenceFailure document may be persisted ONLY after that cleanup succeeds.
"""
import copy
import hashlib
import json
import re


class EvidenceFailure(RuntimeError):
    def __init__(self, gate, document):
        super().__init__(gate)
        self.document = document


def primitive(value):
    """Reject non-catalog objects; do not stringify arbitrary objects/errors."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) in (list, tuple):
        return [primitive(item) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: primitive(item) for key, item in value.items()}
    raise ValueError('CATALOG_PRIMITIVE_TYPE')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


class EvidenceConnection:
    MAX_SELECTS = 1500
    MAX_ROWS = 50000
    MAX_BYTES = 32 * 1024 * 1024

    def __init__(self, connection, statement_factory, *, tls_verified,
                 target_verified, read_only_verified, approved_sources=()):
        if any(value is not True for value in
               (tls_verified, target_verified, read_only_verified)):
            raise ValueError('COLLECTION_BOUNDARY_UNVERIFIED')
        self._connection = connection
        self._statement = statement_factory
        self._approved_sources = frozenset(approved_sources)
        self._observations = []
        self._routine_sets = []
        self._rows = self._bytes = 0
        self._finished = False
        self._retained_document = None

    def _redact(self, value):
        if type(value) is dict:
            output = {}
            for key, item in value.items():
                if key in ('source', 'prosrc') and type(item) is str and item not in self._approved_sources:
                    output[key + '_sha256'] = hashlib.sha256(item.encode('utf-8')).hexdigest()
                    output[key + '_disclosure'] = 'UNREVIEWED_SOURCE_HASH_ONLY'
                elif key == 'proconfig' and item is not None:
                    output[key + '_sha256'] = hashlib.sha256(canonical(item).encode('utf-8')).hexdigest()
                    output[key + '_disclosure'] = 'CONFIG_HASH_ONLY'
                else:
                    output[key] = self._redact(item)
            return output
        if type(value) is list:
            return [self._redact(item) for item in value]
        return value

    def _reserve(self, entry, count):
        size = len(canonical(entry).encode('utf-8'))
        if self._rows + count > self.MAX_ROWS or self._bytes + size > self.MAX_BYTES:
            raise ValueError('EVIDENCE_BOUND_EXCEEDED')
        self._rows += count
        self._bytes += size

    def execute(self, statement, params=None):
        if self._finished:
            raise ValueError('COLLECTION_ALREADY_FINALIZED')
        sql = str(statement).strip()
        if sql in ('SHOW server_version', 'SHOW server_version_num'):
            sql = "SELECT pg_catalog.current_setting('" + sql[5:] + "')"
            statement = self._statement(sql)
        # SELECT must be a complete ASCII keyword followed by SQL whitespace.
        # This is lexical recognition, not authorization of arbitrary SELECT SQL.
        if not re.match(r'\ASELECT[ \t\r\n\f\v]', sql, re.I | re.ASCII) or ';' in sql or re.search(
                r'\b(pg_policies|pg_get_expr|pg_get_viewdef|pg_try_advisory|pg_current_xact_id)\b', sql, re.I):
            raise ValueError('REVIEWED_SELECT_REQUIRED')
        # SQL must come from the separately reviewed projection set, never input.
        params = primitive(params or {})
        if set(params) - {'ids', 'oid', 'role', 'schema', 'classid', 'helper_oids'}:
            raise ValueError('UNREVIEWED_QUERY_PARAMETER')
        if len(self._observations) >= self.MAX_SELECTS:
            raise ValueError('EVIDENCE_BOUND_EXCEEDED')
        data = primitive([dict(row) for row in
                          self._connection.execute(statement, params).mappings().all()])
        entry = {'sql': sql, 'sql_sha256': hashlib.sha256(sql.encode()).hexdigest(),
                 'parameters': params, 'rows': self._redact(data)}
        self._reserve(entry, len(data))
        self._observations.append(entry)  # BEFORE any caller compatibility assertion.

        class Result:
            def mappings(self): return self
            def all(self): return data
        return Result()

    def scalar(self, statement, params=None):
        rows = self.execute(statement, params).all()
        return next(iter(rows[0].values())) if rows else None

    def observe_routine_sets(self, expected, observed):
        if self._finished:
            raise ValueError('COLLECTION_ALREADY_FINALIZED')
        expected = sorted(primitive(list(expected)), key=canonical)
        observed = sorted(primitive(list(observed)), key=canonical)
        # Identity is exactly (schema, name, prokind, ordered input type identities).
        for identity in expected + observed:
            if (type(identity) is not list or len(identity) != 4 or
                any(type(v) is not str for v in identity[:3]) or
                type(identity[3]) is not list or any(type(t) is not list or
                len(t) != 2 or any(type(v) is not str for v in t) for t in identity[3])):
                raise ValueError('ROUTINE_IDENTITY_TYPE')
        e = {canonical(v): v for v in expected}
        o = {canonical(v): v for v in observed}
        entry = {'expected_count': len(expected), 'observed_count': len(observed),
                 'expected_identities': expected, 'observed_identities': observed,
                 'added_identities': [o[k] for k in sorted(o.keys() - e.keys())],
                 'missing_identities': [e[k] for k in sorted(e.keys() - o.keys())]}
        self._reserve(entry, 0)
        self._routine_sets.append(entry)

    def _document(self, complete, gate):
        self._finished = True
        self._retained_document = copy.deepcopy({'schema': 'jous.step7.readonly-retention',
            'status': 'COMPLETE_PRE_MIGRATION_COLLECTION' if complete else 'INCOMPLETE_FAIL_CLOSED',
            'collection_complete': complete, 'execution_approved': False,
            'migration_ready': False, 'failure_gate': gate,
            'failure_reason': None if complete else 'A reviewed collection gate failed; observations are incomplete and not approved.',
            'verified_boundary': {'client_tls': True, 'target': True, 'transaction_read_only': True},
            'observations': self._observations, 'public_routine_sets': self._routine_sets,
            'post_0002_raw_policy_contract': None})
        return copy.deepcopy(self._retained_document)

    def retained_document(self):
        return copy.deepcopy(self._retained_document)

    def failure_document(self, gate):
        if re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', gate) is None:
            gate = 'COLLECTOR_EXCEPTION'
        # Preserve an already-latched collection failure and its original code.
        if self._retained_document is not None and self._retained_document['collection_complete'] is False:
            return self.retained_document()
        return self._document(False, gate)

    def collect(self, callback, failure_type):
        """callback must run ALL reviewed pre-migration gates; never migration code.

        No exception details are serialized. Only an explicitly supplied fixed-code
        gate exception type may supply its reviewed uppercase failure category.
        This method never catches a failure and returns a successful result.
        """
        if self._finished:
            raise ValueError('COLLECTION_ALREADY_FINALIZED')
        try:
            callback(self)
        except BaseException as error:
            gate = str(error) if type(error) is failure_type else 'COLLECTOR_EXCEPTION'
            if re.fullmatch(r'[A-Z][A-Z0-9_]{0,79}', gate) is None:
                gate = 'COLLECTOR_EXCEPTION'
            raise EvidenceFailure(gate, self._document(False, gate)) from None
        return self._document(True, None)
