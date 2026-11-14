-- CORE.1A OFFLINE ARTIFACT ONLY. No installer or resource/adoption bootstrap.
-- Physical/logical mapping: incarnation, slot, lifecycle, admission, claim,
-- publication, activation, history, material, locator correspond one-to-one to
-- realization section 8. lifecycle_binding is the complete copied Lifecycle
-- group; original_binding is the immutable complete original input projection.
-- References are external {id,sha256}, never fictitious local root FKs.
-- Installation is separately authorized, atomic, and requires independent
-- review of owners, exact grants, SQL digest, PostgreSQL build and settings.
BEGIN;
CREATE ROLE jous_table_owner NOLOGIN NOINHERIT;
CREATE ROLE jous_effect_owner NOLOGIN NOINHERIT;
CREATE ROLE jous_custody_owner NOLOGIN NOINHERIT;
CREATE ROLE jous_observe_owner NOLOGIN NOINHERIT;
CREATE ROLE jous_broker NOLOGIN NOINHERIT;
CREATE ROLE jous_custody NOLOGIN NOINHERIT;
CREATE ROLE jous_observer NOLOGIN NOINHERIT;
CREATE SCHEMA jous_authority AUTHORIZATION jous_table_owner;
REVOKE ALL ON SCHEMA jous_authority FROM PUBLIC;
GRANT USAGE ON SCHEMA jous_authority TO jous_effect_owner, jous_custody_owner,
    jous_observe_owner, jous_broker, jous_custody, jous_observer;

CREATE DOMAIN jous_authority.id AS text CHECK
    (octet_length(VALUE) BETWEEN 1 AND 255 AND VALUE !~ '^\s*$');
CREATE DOMAIN jous_authority.counter AS bigint CHECK (VALUE >= 0);
CREATE DOMAIN jous_authority.ref AS jsonb CHECK
    (jsonb_typeof(VALUE) = 'object' AND VALUE ?& ARRAY['identity','sha256']
     AND (VALUE - ARRAY['identity','sha256']) = '{}'::jsonb
     AND jsonb_typeof(VALUE->'identity') = 'string'
     AND octet_length(VALUE->>'identity') BETWEEN 1 AND 255
     AND VALUE->>'identity' !~ '^\s*$'
     AND jsonb_typeof(VALUE->'sha256') = 'string'
     AND VALUE->>'sha256' ~ '^[0-9a-f]{64}$');

CREATE TABLE jous_authority.incarnation (
    namespace jous_authority.id NOT NULL,
    incarnation_id jous_authority.id NOT NULL,
    resource_ref jous_authority.ref NOT NULL,
    configuration_ref jous_authority.ref NOT NULL,
    selection_ref jous_authority.ref NOT NULL,
    qualification_ref jous_authority.ref NOT NULL,
    adoption_ref jous_authority.ref NOT NULL,
    status text NOT NULL CHECK (status IN ('NON_AUTHORITATIVE','ADOPTED','QUARANTINED')),
    fence_epoch jous_authority.counter NOT NULL,
    PRIMARY KEY(namespace,incarnation_id),
    UNIQUE(namespace,incarnation_id,configuration_ref,adoption_ref,fence_epoch)
);
CREATE TABLE jous_authority.slot (
    namespace jous_authority.id NOT NULL,
    incarnation_id jous_authority.id NOT NULL,
    register_id jous_authority.id NOT NULL,
    lifecycle_binding jsonb,
    state text NOT NULL CHECK (state IN ('AUTHORITATIVE_ABSENT','ACTIVE','QUARANTINED')),
    generation bigint NOT NULL CHECK (generation IN (0,1)),
    state_version jous_authority.counter NOT NULL,
    fence_value jous_authority.counter NOT NULL,
    absence_evidence_ref jous_authority.ref NOT NULL,
    PRIMARY KEY(namespace,incarnation_id,register_id),
    UNIQUE(namespace,incarnation_id,register_id,lifecycle_binding),
    FOREIGN KEY(namespace,incarnation_id) REFERENCES jous_authority.incarnation,
    CHECK ((state='AUTHORITATIVE_ABSENT' AND generation=0) OR
           (state='ACTIVE' AND generation=1) OR state='QUARANTINED')
);
CREATE TABLE jous_authority.lifecycle (
    namespace jous_authority.id NOT NULL,
    incarnation_id jous_authority.id NOT NULL,
    register_id jous_authority.id NOT NULL,
    generation bigint NOT NULL CHECK (generation=1),
    K jous_authority.id NOT NULL,
    lifecycle_binding jsonb NOT NULL,
    projection text NOT NULL CHECK (projection IN
        ('RESERVED','CHECKPOINT_RECORDED','ACTIVATION_RECORDED','QUARANTINED')),
    PRIMARY KEY(namespace,incarnation_id,register_id,generation),
    UNIQUE(namespace,register_id,generation), UNIQUE(namespace,K),
    UNIQUE(namespace,incarnation_id,register_id,generation,lifecycle_binding),
    FOREIGN KEY(namespace,incarnation_id,register_id,lifecycle_binding)
        REFERENCES jous_authority.slot(namespace,incarnation_id,register_id,lifecycle_binding)
);
CREATE TABLE jous_authority.admission (
    namespace jous_authority.id NOT NULL,
    incarnation_id jous_authority.id NOT NULL,
    operation_id jous_authority.id NOT NULL,
    admission_id jous_authority.id NOT NULL,
    register_id jous_authority.id NOT NULL,
    generation bigint NOT NULL CHECK(generation=1),
    lifecycle_binding jsonb NOT NULL,
    operation_role text NOT NULL CHECK(operation_role IN ('CHECKPOINT_PUBLICATION','ACTIVATION_CAS')),
    input_binding_ref jous_authority.ref NOT NULL,
    original_binding jsonb NOT NULL,
    state text NOT NULL DEFAULT 'ADMITTED' CHECK(state='ADMITTED'),
    PRIMARY KEY(namespace,incarnation_id,operation_id),
    UNIQUE(namespace,operation_id), UNIQUE(namespace,incarnation_id,admission_id),
    UNIQUE(namespace,incarnation_id,register_id,generation,operation_role),
    UNIQUE(namespace,incarnation_id,operation_id,admission_id,register_id,generation,
           lifecycle_binding,operation_role,input_binding_ref),
    FOREIGN KEY(namespace,incarnation_id,register_id,generation,lifecycle_binding)
      REFERENCES jous_authority.lifecycle(namespace,incarnation_id,register_id,generation,lifecycle_binding)
);
CREATE TABLE jous_authority.claim (
    namespace jous_authority.id NOT NULL,
    incarnation_id jous_authority.id NOT NULL,
    dispatch_claim_id jous_authority.id NOT NULL,
    operation_id jous_authority.id NOT NULL,
    admission_id jous_authority.id NOT NULL,
    register_id jous_authority.id NOT NULL,
    generation bigint NOT NULL CHECK(generation=1),
    lifecycle_binding jsonb NOT NULL,
    operation_role text NOT NULL CHECK(operation_role IN ('CHECKPOINT_PUBLICATION','ACTIVATION_CAS')),
    input_binding_ref jous_authority.ref NOT NULL,
    broker_principal_id jous_authority.id NOT NULL,
    state text NOT NULL DEFAULT 'CLAIMED' CHECK(state='CLAIMED'),
    claim_fence_value jous_authority.counter NOT NULL,
    PRIMARY KEY(namespace,incarnation_id,dispatch_claim_id),
    UNIQUE(namespace,incarnation_id,operation_id), UNIQUE(namespace,incarnation_id,admission_id),
    UNIQUE(namespace,incarnation_id,dispatch_claim_id,operation_id,admission_id,register_id,
           generation,lifecycle_binding,operation_role,input_binding_ref,claim_fence_value),
    FOREIGN KEY(namespace,incarnation_id,operation_id,admission_id,register_id,generation,
                lifecycle_binding,operation_role,input_binding_ref)
      REFERENCES jous_authority.admission(namespace,incarnation_id,operation_id,admission_id,
        register_id,generation,lifecycle_binding,operation_role,input_binding_ref)
);
CREATE TABLE jous_authority.publication (
    LIKE jous_authority.claim INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    original_binding jsonb NOT NULL,
    C0_ref jous_authority.ref NOT NULL, P_ref jous_authority.ref NOT NULL,
    Q_ref jous_authority.ref NOT NULL, host_ref jous_authority.ref NOT NULL,
    decision text NOT NULL CHECK(decision IN ('PUBLISHED','REJECTED')),
    resulting_state_version jous_authority.counter NOT NULL,
    PRIMARY KEY(namespace,incarnation_id,operation_id),
    UNIQUE(namespace,incarnation_id,register_id,generation),
    UNIQUE(namespace,incarnation_id,operation_id,register_id,generation,lifecycle_binding),
    FOREIGN KEY(namespace,incarnation_id,dispatch_claim_id,operation_id,admission_id,register_id,
                generation,lifecycle_binding,operation_role,input_binding_ref,claim_fence_value)
      REFERENCES jous_authority.claim(namespace,incarnation_id,dispatch_claim_id,operation_id,
        admission_id,register_id,generation,lifecycle_binding,operation_role,input_binding_ref,claim_fence_value),
    CHECK(operation_role='CHECKPOINT_PUBLICATION')
);
CREATE TABLE jous_authority.activation (
    LIKE jous_authority.claim INCLUDING DEFAULTS INCLUDING CONSTRAINTS,
    publication_operation_id jous_authority.id NOT NULL,
    original_binding jsonb NOT NULL,
    payload_bytes bytea NOT NULL, payload_sha256 bytea NOT NULL CHECK(octet_length(payload_sha256)=32),
    expected_state text NOT NULL CHECK(expected_state='AUTHORITATIVE_ABSENT'),
    expected_generation bigint NOT NULL CHECK(expected_generation=0),
    expected_state_version jous_authority.counter NOT NULL,
    decision text NOT NULL CHECK(decision IN ('ACTIVATED','REJECTED')),
    resulting_state_version jous_authority.counter NOT NULL,
    PRIMARY KEY(namespace,incarnation_id,operation_id),
    UNIQUE(namespace,incarnation_id,register_id,generation),
    FOREIGN KEY(namespace,incarnation_id,dispatch_claim_id,operation_id,admission_id,register_id,
                generation,lifecycle_binding,operation_role,input_binding_ref,claim_fence_value)
      REFERENCES jous_authority.claim(namespace,incarnation_id,dispatch_claim_id,operation_id,
        admission_id,register_id,generation,lifecycle_binding,operation_role,input_binding_ref,claim_fence_value),
    FOREIGN KEY(namespace,incarnation_id,publication_operation_id,register_id,generation,lifecycle_binding)
      REFERENCES jous_authority.publication(namespace,incarnation_id,operation_id,register_id,generation,lifecycle_binding),
    CHECK(operation_role='ACTIVATION_CAS'), CHECK(sha256(payload_bytes)=payload_sha256)
);
CREATE TABLE jous_authority.locator (
    namespace jous_authority.id NOT NULL,
    incarnation_id jous_authority.id NOT NULL,
    evidence_identity jous_authority.id NOT NULL,
    custody_attempt_id jous_authority.id NOT NULL,
    raw_sha256 bytea NOT NULL CHECK(octet_length(raw_sha256)=32),
    raw_size jous_authority.counter NOT NULL CHECK(raw_size<=8388608),
    evidence_role jous_authority.id NOT NULL, issuer_id jous_authority.id NOT NULL,
    subject_context_ref jous_authority.ref NOT NULL,
    custody_role jous_authority.id NOT NULL, bucket_resource_ref jous_authority.ref NOT NULL,
    object_key text NOT NULL CHECK(octet_length(object_key) BETWEEN 1 AND 1024),
    retention_mode text NOT NULL CHECK(retention_mode='COMPLIANCE'),
    required_retention_until bigint NOT NULL, retention_requirement_ref jous_authority.ref NOT NULL,
    reserved_binding jsonb NOT NULL,
    state text NOT NULL CHECK(state IN ('RESERVED','BOUND')),
    version_id text, observed_retention_until bigint,
    retention_evidence_ref jous_authority.ref, upload_response_ref jous_authority.ref,
    exact_version_readback_ref jous_authority.ref, custody_authentication_ref jous_authority.ref,
    PRIMARY KEY(namespace,incarnation_id,evidence_identity), UNIQUE(namespace,evidence_identity),
    UNIQUE(namespace,incarnation_id,custody_attempt_id),
    UNIQUE(namespace,incarnation_id,bucket_resource_ref,object_key),
    FOREIGN KEY(namespace,incarnation_id) REFERENCES jous_authority.incarnation,
    CHECK((state='RESERVED' AND version_id IS NULL AND observed_retention_until IS NULL
           AND retention_evidence_ref IS NULL AND upload_response_ref IS NULL
           AND exact_version_readback_ref IS NULL AND custody_authentication_ref IS NULL)
       OR (state='BOUND' AND version_id IS NOT NULL AND version_id NOT IN ('','null')
           AND observed_retention_until IS NOT NULL AND observed_retention_until>=required_retention_until
           AND retention_evidence_ref IS NOT NULL AND upload_response_ref IS NOT NULL
           AND exact_version_readback_ref IS NOT NULL AND custody_authentication_ref IS NOT NULL))
);
CREATE TABLE jous_authority.history (
    namespace jous_authority.id NOT NULL, incarnation_id jous_authority.id NOT NULL,
    subject_kind text NOT NULL CHECK(subject_kind IN ('OPERATION','CUSTODY')),
    subject_id jous_authority.id NOT NULL, sequence bigint NOT NULL,
    previous_sequence bigint, operation_id jous_authority.id, evidence_identity jous_authority.id,
    decision text NOT NULL, decision_raw bytea NOT NULL, decision_ref jous_authority.ref NOT NULL,
    PRIMARY KEY(namespace,incarnation_id,subject_kind,subject_id,sequence),
    FOREIGN KEY(namespace,incarnation_id,subject_kind,subject_id,previous_sequence)
      REFERENCES jous_authority.history(namespace,incarnation_id,subject_kind,subject_id,sequence),
    FOREIGN KEY(namespace,incarnation_id,operation_id) REFERENCES jous_authority.admission,
    FOREIGN KEY(namespace,incarnation_id,evidence_identity) REFERENCES jous_authority.locator,
    CHECK((sequence=0 AND previous_sequence IS NULL) OR (sequence>0 AND previous_sequence IS NOT NULL AND previous_sequence=sequence-1)),
    CHECK((subject_kind='OPERATION' AND operation_id IS NOT NULL AND operation_id=subject_id AND evidence_identity IS NULL
       AND ((sequence=0 AND decision='ADMITTED') OR (sequence=1 AND decision='CLAIMED')
         OR (sequence=2 AND decision IN ('CHECKPOINT_PUBLISHED','CHECKPOINT_REJECTED','ACTIVATED','ACTIVATION_REJECTED'))))
     OR (subject_kind='CUSTODY' AND evidence_identity IS NOT NULL AND evidence_identity=subject_id AND operation_id IS NULL
       AND ((sequence=0 AND decision='CUSTODY_RESERVED') OR (sequence=1 AND decision='CUSTODY_BOUND')))),
    CHECK(encode(sha256(decision_raw),'hex')=decision_ref->>'sha256')
);
CREATE TABLE jous_authority.material (
    namespace jous_authority.id NOT NULL, incarnation_id jous_authority.id NOT NULL,
    material_id jous_authority.id NOT NULL, evidence_identity jous_authority.id NOT NULL,
    parent_kind text NOT NULL CHECK(parent_kind IN ('DECISION','READBACK')),
    subject_kind text, subject_id jous_authority.id, sequence bigint,
    activation_operation_id jous_authority.id,
    request_id jous_authority.id NOT NULL, receipt_role jous_authority.id NOT NULL,
    original_raw bytea NOT NULL CHECK(octet_length(original_raw)<=8388608),
    raw_sha256 bytea NOT NULL CHECK(octet_length(raw_sha256)=32),
    issuer_id jous_authority.id NOT NULL, authentication_ref jous_authority.ref NOT NULL,
    subject_ref jous_authority.ref NOT NULL,
    PRIMARY KEY(namespace,incarnation_id,material_id), UNIQUE(namespace,evidence_identity),
    UNIQUE NULLS NOT DISTINCT(namespace,incarnation_id,parent_kind,subject_kind,subject_id,
                             sequence,activation_operation_id,request_id,receipt_role),
    FOREIGN KEY(namespace,incarnation_id,subject_kind,subject_id,sequence) REFERENCES jous_authority.history,
    FOREIGN KEY(namespace,incarnation_id,activation_operation_id) REFERENCES jous_authority.activation,
    CHECK((parent_kind='DECISION' AND subject_kind IS NOT NULL AND subject_id IS NOT NULL
           AND sequence IS NOT NULL AND activation_operation_id IS NULL)
       OR (parent_kind='READBACK' AND subject_kind IS NULL AND subject_id IS NULL
           AND sequence IS NULL AND activation_operation_id IS NOT NULL)),
    CHECK(sha256(original_raw)=raw_sha256)
);

-- Every protected table is logged by default; no TTL, cleanup, release or reset.
CREATE FUNCTION jous_authority.immutable() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
BEGIN RAISE EXCEPTION 'IMMUTABLE_AUTHORITY_ROW'; END $$;
CREATE TRIGGER immutable_admission BEFORE UPDATE OR DELETE ON jous_authority.admission
FOR EACH ROW EXECUTE FUNCTION jous_authority.immutable();
CREATE TRIGGER immutable_claim BEFORE UPDATE OR DELETE ON jous_authority.claim
FOR EACH ROW EXECUTE FUNCTION jous_authority.immutable();
CREATE TRIGGER immutable_publication BEFORE UPDATE OR DELETE ON jous_authority.publication
FOR EACH ROW EXECUTE FUNCTION jous_authority.immutable();
CREATE TRIGGER immutable_activation BEFORE UPDATE OR DELETE ON jous_authority.activation
FOR EACH ROW EXECUTE FUNCTION jous_authority.immutable();
CREATE TRIGGER immutable_history BEFORE UPDATE OR DELETE ON jous_authority.history
FOR EACH ROW EXECUTE FUNCTION jous_authority.immutable();
CREATE TRIGGER immutable_material BEFORE UPDATE OR DELETE ON jous_authority.material
FOR EACH ROW EXECUTE FUNCTION jous_authority.immutable();

CREATE FUNCTION jous_authority.transition_guard() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
BEGIN
 IF TG_OP='DELETE' THEN RAISE EXCEPTION 'NO_ELIGIBILITY_RECREATION'; END IF;
 IF TG_TABLE_NAME='locator' THEN
   IF OLD.state<>'RESERVED' OR NEW.state<>'BOUND' OR
      (to_jsonb(OLD)-ARRAY['state','version_id','observed_retention_until','retention_evidence_ref',
       'upload_response_ref','exact_version_readback_ref','custody_authentication_ref']) IS DISTINCT FROM
      (to_jsonb(NEW)-ARRAY['state','version_id','observed_retention_until','retention_evidence_ref',
       'upload_response_ref','exact_version_readback_ref','custody_authentication_ref']) THEN
     RAISE EXCEPTION 'IMMUTABLE_CUSTODY_BINDING'; END IF;
 ELSIF TG_TABLE_NAME='slot' THEN
   IF (OLD.namespace,OLD.incarnation_id,OLD.register_id,OLD.absence_evidence_ref) IS DISTINCT FROM
      (NEW.namespace,NEW.incarnation_id,NEW.register_id,NEW.absence_evidence_ref)
      OR (OLD.lifecycle_binding IS NOT NULL AND OLD.lifecycle_binding IS DISTINCT FROM NEW.lifecycle_binding)
      OR NEW.state_version<OLD.state_version OR NEW.fence_value<OLD.fence_value
      OR NEW.generation<OLD.generation OR (OLD.state='ACTIVE' AND NEW.state NOT IN ('ACTIVE','QUARANTINED'))
      OR (OLD.state='QUARANTINED' AND NEW.state<>'QUARANTINED') THEN RAISE EXCEPTION 'SLOT_REGRESSION'; END IF;
 ELSIF TG_TABLE_NAME='lifecycle' THEN
   IF (to_jsonb(OLD)-'projection') IS DISTINCT FROM (to_jsonb(NEW)-'projection')
      OR NOT ((OLD.projection='RESERVED' AND NEW.projection IN ('CHECKPOINT_RECORDED','QUARANTINED'))
       OR (OLD.projection='CHECKPOINT_RECORDED' AND NEW.projection IN ('ACTIVATION_RECORDED','QUARANTINED')))
     THEN RAISE EXCEPTION 'LIFECYCLE_REGRESSION'; END IF;
 ELSIF TG_TABLE_NAME='incarnation' THEN
   IF (to_jsonb(OLD)-ARRAY['status','fence_epoch']) IS DISTINCT FROM (to_jsonb(NEW)-ARRAY['status','fence_epoch'])
     OR NEW.fence_epoch<OLD.fence_epoch OR NOT
       ((OLD.status='NON_AUTHORITATIVE' AND NEW.status IN ('ADOPTED','QUARANTINED'))
        OR (OLD.status='ADOPTED' AND NEW.status='QUARANTINED')) THEN RAISE EXCEPTION 'INCARNATION_REWRITE'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER guard_slot BEFORE UPDATE OR DELETE ON jous_authority.slot
FOR EACH ROW EXECUTE FUNCTION jous_authority.transition_guard();
CREATE TRIGGER guard_lifecycle BEFORE UPDATE OR DELETE ON jous_authority.lifecycle
FOR EACH ROW EXECUTE FUNCTION jous_authority.transition_guard();
CREATE TRIGGER guard_locator BEFORE UPDATE OR DELETE ON jous_authority.locator
FOR EACH ROW EXECUTE FUNCTION jous_authority.transition_guard();
CREATE TRIGGER guard_incarnation BEFORE UPDATE OR DELETE ON jous_authority.incarnation
FOR EACH ROW EXECUTE FUNCTION jous_authority.transition_guard();

CREATE FUNCTION jous_authority.history_role_guard() RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE role text;
BEGIN
 IF NEW.subject_kind='OPERATION' AND NEW.sequence=2 THEN
   SELECT operation_role INTO STRICT role FROM jous_authority.admission WHERE namespace=NEW.namespace
       AND incarnation_id=NEW.incarnation_id AND operation_id=NEW.operation_id;
   IF (role='CHECKPOINT_PUBLICATION' AND NEW.decision NOT IN ('CHECKPOINT_PUBLISHED','CHECKPOINT_REJECTED'))
     OR (role='ACTIVATION_CAS' AND NEW.decision NOT IN ('ACTIVATED','ACTIVATION_REJECTED')) THEN
     RAISE EXCEPTION 'HISTORY_ROLE_MISMATCH'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER history_role BEFORE INSERT ON jous_authority.history
FOR EACH ROW EXECUTE FUNCTION jous_authority.history_role_guard();

CREATE FUNCTION jous_authority.check_request(r jsonb, op text) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE names text[]; lifecycle text[]:=ARRAY['register_id','generation','activation_id','K','J','host_ref','scope_ref'];
 original text[]:=ARRAY['operation_id','operation_role','input_binding_ref'];
 fresh text[]:=ARRAY['time_evidence_ref','qualification_ref'];
 snapshot text[]:=ARRAY['E_bytes','S0_bytes','C0_bytes','P_bytes','E_ref','S0_ref','C0_ref','P_ref','Q_bytes','Q_ref'];
 absence text[]:=ARRAY['absence_history_ref','original_history_ref','expected_state','expected_generation','expected_state_version'];
 admission text[]:=ARRAY['admission_id','admission_evidence_ref'];
 claim text[]:=ARRAY['dispatch_claim_id','claim_fence_value','claim_commit_evidence_ref'];
 payload text[]:=ARRAY['payload_bytes','payload_sha256','publication_operation_id','publication_decision_ref','publication_receipt_ref'];
 custody text[]:=ARRAY['evidence_identity','raw_sha256','raw_size','evidence_role','issuer_id','subject_context_ref',
  'custody_attempt_id','custody_role','bucket_resource_ref','object_key','retention_mode','required_retention_until','retention_requirement_ref'];
 n text; v jsonb; unused jous_authority.ref;
BEGIN
 names:=ARRAY['schema_version','operation','request_id','namespace','incarnation_id','configuration_ref',
  'adoption_ref','expected_fence_epoch','principal_id','credential_identity','logical_role','authorization_ref'];
 IF op='ORIGINAL_ATTEMPT_ADMISSION' THEN names:=names||fresh||lifecycle||original||snapshot||absence||ARRAY['admission_id'];
   IF r->>'operation_role'='ACTIVATION_CAS' THEN names:=names||payload; END IF;
 ELSIF op='DISPATCH_CLAIM' THEN names:=names||fresh||lifecycle||original||admission||
   ARRAY['dispatch_claim_id','broker_principal_id','expected_fence_value'];
 ELSIF op IN ('CHECKPOINT_PUBLICATION','ACTIVATION_CAS') THEN names:=names||fresh||lifecycle||original||snapshot||absence||admission||claim;
   IF op='ACTIVATION_CAS' THEN names:=names||payload; END IF;
 ELSIF op='AUTHORITATIVE_READBACK' THEN names:=names||fresh||lifecycle||original||payload||
   ARRAY['observation_authorization_ref','observation_scope_ref','activation_decision_ref','activation_receipt_ref','minimum_state_version'];
 ELSIF op='READ_ONLY_RESOLUTION' THEN names:=names||ARRAY['observation_authorization_ref','observation_scope_ref','target_kind','permitted_outputs'];
   IF r->>'target_kind'='OPERATION' THEN names:=names||ARRAY['operation_id'];
   ELSIF r->>'target_kind'='EVIDENCE' THEN names:=names||ARRAY['evidence_identity']; ELSE RAISE EXCEPTION 'INVALID_TARGET'; END IF;
 ELSIF op='EVIDENCE_CUSTODY_BINDING' THEN names:=names||fresh||custody||ARRAY['phase'];
   IF r->>'phase'='RESERVE' THEN names:=names||ARRAY['raw_bytes'];
   ELSIF r->>'phase'='BIND' THEN names:=names||ARRAY['version_id','observed_retention_until','retention_evidence_ref',
     'upload_response_ref','exact_version_readback_ref','custody_authentication_ref']; ELSE RAISE EXCEPTION 'INVALID_PHASE'; END IF;
 ELSE RAISE EXCEPTION 'INVALID_OPERATION'; END IF;
 IF jsonb_typeof(r)<>'object' OR NOT(r ?& names) OR (r-names)<>'{}'::jsonb
    OR r->>'operation'<>op THEN RAISE EXCEPTION 'CLOSED_REQUEST_SCHEMA'; END IF;
 FOREACH n IN ARRAY names LOOP
   v:=r->n;
   IF v='null'::jsonb THEN RAISE EXCEPTION 'NULL_REQUEST_MEMBER'; END IF;
   IF n LIKE '%\_ref' ESCAPE '\' THEN unused:=v;
   ELSIF n IN ('schema_version','expected_fence_epoch','generation','expected_generation','expected_state_version',
      'claim_fence_value','expected_fence_value','minimum_state_version','raw_size') THEN
     IF jsonb_typeof(v)<>'number' OR v::text !~ '^[0-9]+$' THEN RAISE EXCEPTION 'INTEGER_DOMAIN'; END IF;
     PERFORM (v::text)::jous_authority.counter;
   ELSIF n IN ('required_retention_until','observed_retention_until') THEN
     IF jsonb_typeof(v)<>'number' OR v::text !~ '^-?[0-9]+$' THEN RAISE EXCEPTION 'UTC_DOMAIN'; END IF;
     PERFORM (v::text)::bigint;
   ELSIF n IN ('raw_sha256','payload_sha256') THEN
     IF jsonb_typeof(v)<>'string' OR r->>n !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'DIGEST_DOMAIN'; END IF;
   ELSIF n LIKE '%\_bytes' ESCAPE '\' THEN
     IF jsonb_typeof(v)<>'string' OR r->>n !~ '^([0-9a-f]{2})*$' OR length(r->>n)>16777216 THEN RAISE EXCEPTION 'BYTES_DOMAIN'; END IF;
   ELSIF n='permitted_outputs' THEN
     IF jsonb_typeof(v)<>'array' OR jsonb_array_length(v) NOT BETWEEN 1 AND 5 OR
       EXISTS(SELECT 1 FROM jsonb_array_elements_text(v) x WHERE x NOT IN
         ('OPERATION_STATE','DECISION','RECEIPT_REFERENCE','CUSTODY_LOCATOR','AUTHORITATIVE_READBACK_FACTS'))
       OR (SELECT count(*) FROM jsonb_array_elements_text(v))<>(SELECT count(DISTINCT x) FROM jsonb_array_elements_text(v) x)
       THEN RAISE EXCEPTION 'CLOSED_OUTPUTS'; END IF;
   ELSIF n IN ('object_key','version_id') THEN
     IF jsonb_typeof(v)<>'string' OR octet_length(r->>n) NOT BETWEEN 1 AND 1024 OR
       (n='version_id' AND r->>n='null') THEN RAISE EXCEPTION 'TEXT_DOMAIN'; END IF;
   ELSE
     IF jsonb_typeof(v)<>'string' THEN RAISE EXCEPTION 'IDENTIFIER_TYPE'; END IF;
     PERFORM (r->>n)::jous_authority.id;
   END IF;
 END LOOP;
 IF r->>'schema_version'<>'1' OR (r ? 'generation' AND r->>'generation'<>'1')
   OR (r ? 'expected_generation' AND r->>'expected_generation'<>'0')
   OR (r ? 'expected_state' AND r->>'expected_state'<>'AUTHORITATIVE_ABSENT')
   OR (r ? 'operation_role' AND r->>'operation_role' NOT IN ('CHECKPOINT_PUBLICATION','ACTIVATION_CAS'))
   OR (op='CHECKPOINT_PUBLICATION' AND r->>'operation_role'<>'CHECKPOINT_PUBLICATION')
   OR (op IN ('ACTIVATION_CAS','AUTHORITATIVE_READBACK') AND r->>'operation_role'<>'ACTIVATION_CAS')
   OR (r ? 'retention_mode' AND r->>'retention_mode'<>'COMPLIANCE') THEN RAISE EXCEPTION 'FIXED_LITERAL'; END IF;
END $$;

CREATE FUNCTION jous_authority.lifecycle_of(r jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE
SET search_path=pg_catalog AS $$ SELECT jsonb_build_object('register_id',r->'register_id',
 'generation',r->'generation','activation_id',r->'activation_id','K',r->'K','J',r->'J',
 'host_ref',r->'host_ref','scope_ref',r->'scope_ref') $$;
CREATE FUNCTION jous_authority.original_of(r jsonb) RETURNS jsonb LANGUAGE sql IMMUTABLE
SET search_path=pg_catalog AS $$ SELECT r - ARRAY['operation','request_id','principal_id',
 'credential_identity','logical_role','current_time','time_evidence_ref','qualification_ref',
 'admission_id','admission_evidence_ref','dispatch_claim_id','claim_fence_value',
 'claim_commit_evidence_ref','broker_principal_id','expected_fence_value'] $$;
CREATE FUNCTION jous_authority.reject(reason text) RETURNS jsonb LANGUAGE sql IMMUTABLE
SET search_path=pg_catalog AS $$ SELECT jsonb_build_object('disposition','REJECTED',
 'reason',reason,'prior_decision_ref',NULL) $$;

CREATE FUNCTION jous_authority.check_authority(r jsonb) RETURNS void LANGUAGE plpgsql
SET search_path=pg_catalog AS $$
DECLARE a jous_authority.incarnation;
BEGIN
 -- Shared by every fixed writer/readback path. Hash collisions only serialize
 -- unrelated scopes; the complete incarnation/row comparisons remain decisive.
 PERFORM pg_advisory_xact_lock(hashtextextended(jsonb_build_array(r->'namespace',r->'incarnation_id')::text,0));
 IF current_setting('fsync')<>'on' OR current_setting('full_page_writes')<>'on'
    OR current_setting('synchronous_commit')<>'on' OR pg_is_in_recovery() THEN
   RAISE EXCEPTION 'UNQUALIFIED_SESSION'; END IF;
 SELECT * INTO STRICT a FROM jous_authority.incarnation
  WHERE namespace=r->>'namespace' AND incarnation_id=r->>'incarnation_id';
 IF a.status<>'ADOPTED' OR a.configuration_ref<>r->'configuration_ref'
    OR a.adoption_ref<>r->'adoption_ref' OR a.fence_epoch<>(r->>'expected_fence_epoch')::bigint THEN
   RAISE EXCEPTION 'WRONG_INCARNATION'; END IF;
END $$;

CREATE FUNCTION jous_authority.append_history(r jsonb, kind text, ident text, seq bigint, code text)
RETURNS jsonb LANGUAGE plpgsql SET search_path=pg_catalog AS $$
DECLARE raw bytea; rr jsonb;
BEGIN
 raw:=convert_to(jsonb_build_object('namespace',r->'namespace','incarnation_id',r->'incarnation_id',
     'subject_kind',kind,'subject_id',ident,'sequence',seq,'decision',code,'request',r)::text,'UTF8');
 rr:=jsonb_build_object('identity',encode(sha256(raw),'hex'),'sha256',encode(sha256(raw),'hex'));
 INSERT INTO jous_authority.history VALUES(r->>'namespace',r->>'incarnation_id',kind,ident,seq,
    CASE WHEN seq=0 THEN NULL ELSE seq-1 END,
    CASE WHEN kind='OPERATION' THEN ident ELSE NULL END,
    CASE WHEN kind='CUSTODY' THEN ident ELSE NULL END,code,raw,rr);
 RETURN rr;
END $$;

-- Private effect dispatcher. Only exact wrappers below are granted to broker.
CREATE FUNCTION jous_authority.effect(r jsonb, op text) RETURNS jsonb LANGUAGE plpgsql
SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s jous_authority.slot; a jous_authority.admission; c jous_authority.claim;
 l jsonb; original jsonb; rr jsonb; rejection text; decision_code text;
 ns text:=r->>'namespace'; inc text:=r->>'incarnation_id'; oid text:=r->>'operation_id';
BEGIN
 PERFORM jous_authority.check_request(r,op);
 IF r->>'operation'<>op OR r->>'logical_role'<>'EXECUTOR' OR r->>'schema_version'<>'1' THEN
   RAISE EXCEPTION 'INVALID_INPUT'; END IF;
 PERFORM jous_authority.check_authority(r);
 SELECT * INTO STRICT s FROM jous_authority.slot WHERE namespace=ns AND incarnation_id=inc
   AND register_id=r->>'register_id' FOR UPDATE;
 l:=jous_authority.lifecycle_of(r); original:=jous_authority.original_of(r);
 SELECT * INTO a FROM jous_authority.admission WHERE namespace=ns AND incarnation_id=inc AND operation_id=oid;
 IF op='ORIGINAL_ATTEMPT_ADMISSION' THEN
   IF FOUND THEN RETURN jous_authority.reject(CASE WHEN a.original_binding=original THEN 'DUPLICATE' ELSE 'INPUT_CONFLICT' END); END IF;
   IF s.lifecycle_binding IS NOT NULL AND s.lifecycle_binding<>l THEN RETURN jous_authority.reject('LIFECYCLE_CONFLICT'); END IF;
   IF EXISTS(SELECT 1 FROM jous_authority.admission WHERE namespace=ns AND incarnation_id=inc
      AND register_id=r->>'register_id' AND operation_role=r->>'operation_role') THEN
     RETURN jous_authority.reject('LIFECYCLE_CONFLICT'); END IF;
   IF s.state<>'AUTHORITATIVE_ABSENT' OR s.generation<>0 OR
      s.state_version<>(r->>'expected_state_version')::bigint THEN RETURN jous_authority.reject('WRONG_PREDECESSOR'); END IF;
   IF r->>'operation_role'='ACTIVATION_CAS' AND NOT EXISTS(SELECT 1 FROM jous_authority.publication
      WHERE namespace=ns AND incarnation_id=inc AND operation_id=r->>'publication_operation_id'
      AND lifecycle_binding=l AND decision='PUBLISHED') THEN RETURN jous_authority.reject('UNQUALIFIED'); END IF;
   IF s.lifecycle_binding IS NULL THEN
     UPDATE jous_authority.slot SET lifecycle_binding=l WHERE namespace=ns AND incarnation_id=inc AND register_id=s.register_id;
     INSERT INTO jous_authority.lifecycle VALUES(ns,inc,s.register_id,1,r->>'K',l,'RESERVED');
   END IF;
   INSERT INTO jous_authority.admission VALUES(ns,inc,oid,r->>'admission_id',s.register_id,1,l,
      r->>'operation_role',r->'input_binding_ref',original,'ADMITTED');
   rr:=jous_authority.append_history(r,'OPERATION',oid,0,'ADMITTED');
   RETURN jsonb_build_object('disposition','ADMITTED','operation_id',oid,'admission_id',r->'admission_id',
     'input_binding_ref',r->'input_binding_ref','state_version',s.state_version,'fence_value',s.fence_value,
     'admission_decision_ref',rr);
 END IF;
 IF a.operation_id IS NULL OR a.lifecycle_binding<>l OR a.admission_id<>r->>'admission_id'
    OR a.operation_role<>r->>'operation_role' OR a.input_binding_ref<>r->'input_binding_ref' THEN
   RETURN jous_authority.reject('INPUT_CONFLICT'); END IF;
 SELECT * INTO c FROM jous_authority.claim WHERE namespace=ns AND incarnation_id=inc AND operation_id=oid;
 IF op='DISPATCH_CLAIM' THEN
   IF FOUND THEN RETURN jous_authority.reject(CASE WHEN c.dispatch_claim_id=r->>'dispatch_claim_id'
       AND c.broker_principal_id=r->>'broker_principal_id' THEN 'DUPLICATE' ELSE 'INPUT_CONFLICT' END); END IF;
   IF s.fence_value<>(r->>'expected_fence_value')::bigint THEN RETURN jous_authority.reject('STALE_CONTINUATION'); END IF;
   UPDATE jous_authority.slot SET fence_value=fence_value+1 WHERE namespace=ns AND incarnation_id=inc AND register_id=s.register_id
     RETURNING * INTO s;
   INSERT INTO jous_authority.claim VALUES(ns,inc,r->>'dispatch_claim_id',oid,a.admission_id,s.register_id,
      1,l,a.operation_role,a.input_binding_ref,r->>'broker_principal_id','CLAIMED',s.fence_value);
   rr:=jous_authority.append_history(r,'OPERATION',oid,1,'CLAIMED');
   RETURN jsonb_build_object('disposition','CLAIMED','operation_id',oid,'admission_id',a.admission_id,
     'dispatch_claim_id',r->'dispatch_claim_id','broker_principal_id',r->'broker_principal_id',
     'claim_fence_value',s.fence_value,'claim_decision_ref',rr);
 END IF;
 IF c.dispatch_claim_id IS NULL OR c.dispatch_claim_id<>r->>'dispatch_claim_id'
    OR c.claim_fence_value<>(r->>'claim_fence_value')::bigint OR s.fence_value<>c.claim_fence_value
    OR a.original_binding<>original THEN RETURN jous_authority.reject('INPUT_CONFLICT'); END IF;
 IF EXISTS(SELECT 1 FROM jous_authority.history WHERE namespace=ns AND incarnation_id=inc
      AND subject_kind='OPERATION' AND subject_id=oid AND sequence=2) THEN RETURN jous_authority.reject('DUPLICATE'); END IF;
 IF s.state<>'AUTHORITATIVE_ABSENT' OR s.generation<>0 THEN rejection:='ALREADY_ACTIVE';
 ELSIF s.state_version<>(r->>'expected_state_version')::bigint THEN rejection:='WRONG_PREDECESSOR'; END IF;
 IF op='ACTIVATION_CAS' AND NOT EXISTS(SELECT 1 FROM jous_authority.publication WHERE namespace=ns
     AND incarnation_id=inc AND operation_id=r->>'publication_operation_id' AND lifecycle_binding=l AND decision='PUBLISHED') THEN
   rejection:='UNQUALIFIED'; END IF;
 IF rejection IS NULL THEN
   UPDATE jous_authority.slot SET state_version=state_version+1,
      state=CASE WHEN op='ACTIVATION_CAS' THEN 'ACTIVE' ELSE state END,
      generation=CASE WHEN op='ACTIVATION_CAS' THEN 1 ELSE generation END
    WHERE namespace=ns AND incarnation_id=inc AND register_id=s.register_id RETURNING * INTO s;
 END IF;
 IF op='CHECKPOINT_PUBLICATION' THEN
   INSERT INTO jous_authority.publication SELECT c.*,original,r->'C0_ref',r->'P_ref',r->'Q_ref',r->'host_ref',
      CASE WHEN rejection IS NULL THEN 'PUBLISHED' ELSE 'REJECTED' END,s.state_version;
   decision_code:=CASE WHEN rejection IS NULL THEN 'CHECKPOINT_PUBLISHED' ELSE 'CHECKPOINT_REJECTED' END;
 ELSE
   INSERT INTO jous_authority.activation SELECT c.*,r->>'publication_operation_id',original,
      decode(r->>'payload_bytes','hex'),decode(r->>'payload_sha256','hex'),r->>'expected_state',
      (r->>'expected_generation')::bigint,(r->>'expected_state_version')::bigint,
      CASE WHEN rejection IS NULL THEN 'ACTIVATED' ELSE 'REJECTED' END,s.state_version;
   decision_code:=CASE WHEN rejection IS NULL THEN 'ACTIVATED' ELSE 'ACTIVATION_REJECTED' END;
 END IF;
 rr:=jous_authority.append_history(r,'OPERATION',oid,2,decision_code);
 UPDATE jous_authority.lifecycle SET projection=CASE WHEN op='ACTIVATION_CAS' THEN 'ACTIVATION_RECORDED' ELSE 'CHECKPOINT_RECORDED' END
   WHERE namespace=ns AND incarnation_id=inc AND register_id=s.register_id AND generation=1;
 IF rejection IS NOT NULL THEN RETURN jous_authority.reject(rejection) || jsonb_build_object('prior_decision_ref',rr); END IF;
 RETURN jsonb_build_object('disposition',decision_code,'operation_id',oid,'admission_id',a.admission_id,
    'dispatch_claim_id',c.dispatch_claim_id,'state_version',s.state_version,'fence_value',s.fence_value,
    'decision_ref',rr,'lifecycle_binding',l,'input_binding_ref',a.input_binding_ref);
END $$;

CREATE FUNCTION jous_authority.custody_binding(r jsonb) RETURNS jsonb LANGUAGE plpgsql
SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE v jous_authority.locator; rr jsonb; reserved jsonb; key text;
 ns text:=r->>'namespace'; inc text:=r->>'incarnation_id'; eid text:=r->>'evidence_identity';
BEGIN
 PERFORM jous_authority.check_request(r,'EVIDENCE_CUSTODY_BINDING');
 IF r->>'operation'<>'EVIDENCE_CUSTODY_BINDING' OR r->>'logical_role'<>'CUSTODY' THEN RAISE EXCEPTION 'INVALID_INPUT'; END IF;
 PERFORM jous_authority.check_authority(r);
 -- Serialize identity and deterministic key conflicts; no register mutation.
 PERFORM 1 FROM jous_authority.incarnation WHERE namespace=ns AND incarnation_id=inc;
 key:='evidence/v1/'||encode(convert_to(ns,'UTF8'),'hex')||'/'||encode(convert_to(inc,'UTF8'),'hex')||'/'||
      encode(convert_to(r->>'custody_role','UTF8'),'hex')||'/'||encode(convert_to(eid,'UTF8'),'hex');
 IF key<>r->>'object_key' OR (r->>'raw_size')::bigint>8388608 THEN RETURN jous_authority.reject('SIZE_UNSUPPORTED'); END IF;
 reserved:=r - ARRAY['operation','request_id','phase','raw_bytes','principal_id','credential_identity',
  'logical_role','time_evidence_ref','qualification_ref','version_id','observed_retention_until',
  'retention_evidence_ref','upload_response_ref','exact_version_readback_ref','custody_authentication_ref'];
 SELECT * INTO v FROM jous_authority.locator WHERE namespace=ns AND incarnation_id=inc AND evidence_identity=eid FOR UPDATE;
 IF r->>'phase'='RESERVE' THEN
   IF FOUND THEN RETURN jous_authority.reject(CASE WHEN v.reserved_binding=reserved THEN 'DUPLICATE' ELSE 'CUSTODY_CONFLICT' END); END IF;
   IF octet_length(decode(r->>'raw_bytes','hex'))<>(r->>'raw_size')::bigint OR
      sha256(decode(r->>'raw_bytes','hex'))<>decode(r->>'raw_sha256','hex') THEN RAISE EXCEPTION 'INVALID_INPUT'; END IF;
   IF EXISTS(SELECT 1 FROM jous_authority.locator WHERE namespace=ns AND incarnation_id=inc
       AND bucket_resource_ref=r->'bucket_resource_ref' AND object_key=key) THEN RETURN jous_authority.reject('CUSTODY_CONFLICT'); END IF;
   INSERT INTO jous_authority.locator(namespace,incarnation_id,evidence_identity,custody_attempt_id,
     raw_sha256,raw_size,evidence_role,issuer_id,subject_context_ref,custody_role,bucket_resource_ref,
     object_key,retention_mode,required_retention_until,retention_requirement_ref,reserved_binding,state)
   VALUES(ns,inc,eid,r->>'custody_attempt_id',decode(r->>'raw_sha256','hex'),(r->>'raw_size')::bigint,
     r->>'evidence_role',r->>'issuer_id',r->'subject_context_ref',r->>'custody_role',r->'bucket_resource_ref',
     key,'COMPLIANCE',(r->>'required_retention_until')::bigint,r->'retention_requirement_ref',reserved,'RESERVED');
   rr:=jous_authority.append_history(r - 'raw_bytes','CUSTODY',eid,0,'CUSTODY_RESERVED');
   RETURN jsonb_build_object('disposition','CUSTODY_RESERVED','reservation_decision_ref',rr,
      'custody_attempt_id',r->'custody_attempt_id','evidence_identity',eid,'object_key',key);
 ELSIF r->>'phase'='BIND' THEN
   IF v.evidence_identity IS NULL OR v.reserved_binding<>reserved THEN RETURN jous_authority.reject('CUSTODY_CONFLICT'); END IF;
   IF v.state='BOUND' THEN RETURN jous_authority.reject('DUPLICATE'); END IF;
   UPDATE jous_authority.locator SET state='BOUND',version_id=r->>'version_id',
      observed_retention_until=(r->>'observed_retention_until')::bigint,
      retention_evidence_ref=r->'retention_evidence_ref',upload_response_ref=r->'upload_response_ref',
      exact_version_readback_ref=r->'exact_version_readback_ref',custody_authentication_ref=r->'custody_authentication_ref'
    WHERE namespace=ns AND incarnation_id=inc AND evidence_identity=eid RETURNING * INTO v;
   rr:=jous_authority.append_history(r,'CUSTODY',eid,1,'CUSTODY_BOUND');
   RETURN jsonb_build_object('disposition','CUSTODY_BOUND','locator',to_jsonb(v),'binding_decision_ref',rr,
      'custody_authentication_ref',r->'custody_authentication_ref');
 END IF;
 RAISE EXCEPTION 'INVALID_INPUT';
END $$;

CREATE FUNCTION jous_authority.observe(r jsonb, op text) RETURNS jsonb LANGUAGE plpgsql
SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE s jous_authority.slot; d jous_authority.activation; result jsonb:='{}'; category text;
 ns text:=r->>'namespace'; inc text:=r->>'incarnation_id'; oid text:=r->>'operation_id';
BEGIN
 PERFORM jous_authority.check_request(r,op);
 IF op<>r->>'operation' OR r->>'logical_role' NOT IN ('OBSERVER','RESULT_VERIFIER','CUSTODY') THEN RAISE EXCEPTION 'INVALID_INPUT'; END IF;
 IF op='AUTHORITATIVE_READBACK' THEN
   IF r->>'logical_role' NOT IN ('OBSERVER','RESULT_VERIFIER') THEN RAISE EXCEPTION 'INVALID_OBSERVATION_ROLE'; END IF;
   PERFORM jous_authority.check_authority(r);
   SELECT * INTO STRICT s FROM jous_authority.slot WHERE namespace=ns AND incarnation_id=inc AND register_id=r->>'register_id';
   SELECT * INTO STRICT d FROM jous_authority.activation WHERE namespace=ns AND incarnation_id=inc AND operation_id=oid;
   IF s.state<>'ACTIVE' OR s.generation<>1 OR s.lifecycle_binding<>d.lifecycle_binding
      OR d.lifecycle_binding<>jous_authority.lifecycle_of(r) OR d.decision<>'ACTIVATED'
      OR d.payload_sha256<>decode(r->>'payload_sha256','hex') OR s.state_version<(r->>'minimum_state_version')::bigint
      OR d.publication_operation_id<>r->>'publication_operation_id' THEN RETURN jous_authority.reject('INPUT_CONFLICT'); END IF;
   RETURN jsonb_build_object('disposition','OBSERVED','protected_state',to_jsonb(s),'original_decision',to_jsonb(d),
     'publication_decision_ref',(SELECT decision_ref FROM jous_authority.history WHERE namespace=ns
       AND incarnation_id=inc AND subject_kind='OPERATION' AND subject_id=d.publication_operation_id
       AND sequence=2 AND decision='CHECKPOINT_PUBLISHED'),
     'activation_decision_ref',(SELECT decision_ref FROM jous_authority.history WHERE namespace=ns
       AND incarnation_id=inc AND subject_kind='OPERATION' AND subject_id=oid AND sequence=2 AND decision='ACTIVATED'),
     'publication_receipt_ref',(SELECT authentication_ref FROM jous_authority.material WHERE namespace=ns
       AND incarnation_id=inc AND subject_kind='OPERATION' AND subject_id=d.publication_operation_id
       AND sequence=2 AND receipt_role='RESULT_PUBLICATION'),
     'activation_receipt_ref',(SELECT authentication_ref FROM jous_authority.material WHERE namespace=ns
       AND incarnation_id=inc AND subject_kind='OPERATION' AND subject_id=oid AND sequence=2 AND receipt_role='RESULT_CAS'));
 END IF;
 IF op<>'READ_ONLY_RESOLUTION' THEN RAISE EXCEPTION 'INVALID_INPUT'; END IF;
 -- Broker independently checks observation scope, including explicit permission
 -- to inspect quarantined resources; this read cannot confer effect permission.
 FOR category IN SELECT jsonb_array_elements_text(r->'permitted_outputs') LOOP
   IF category='OPERATION_STATE' AND r->>'target_kind'='OPERATION' THEN
     result:=result||jsonb_build_object(category,(SELECT to_jsonb(a) FROM jous_authority.admission a
       WHERE namespace=ns AND incarnation_id=inc AND operation_id=oid));
   ELSIF category='DECISION' THEN
     result:=result||jsonb_build_object(category,(SELECT jsonb_agg(to_jsonb(h) ORDER BY sequence)
       FROM jous_authority.history h WHERE namespace=ns AND incarnation_id=inc AND subject_id=
       CASE WHEN r->>'target_kind'='OPERATION' THEN oid ELSE r->>'evidence_identity' END
       AND subject_kind=CASE WHEN r->>'target_kind'='OPERATION' THEN 'OPERATION' ELSE 'CUSTODY' END));
   ELSIF category='CUSTODY_LOCATOR' AND r->>'target_kind'='EVIDENCE' THEN
     result:=result||jsonb_build_object(category,(SELECT to_jsonb(v) FROM jous_authority.locator v
       WHERE namespace=ns AND incarnation_id=inc AND evidence_identity=r->>'evidence_identity'));
   ELSIF category IN ('RECEIPT_REFERENCE','AUTHORITATIVE_READBACK_FACTS') THEN
     result:=result||jsonb_build_object(category,(SELECT jsonb_agg(to_jsonb(m)) FROM jous_authority.material m
       WHERE namespace=ns AND incarnation_id=inc AND
       ((r->>'target_kind'='OPERATION' AND (subject_id=oid OR activation_operation_id=oid)) OR
        (r->>'target_kind'='EVIDENCE' AND evidence_identity=r->>'evidence_identity'))
       AND (category<>'AUTHORITATIVE_READBACK_FACTS' OR parent_kind='READBACK')));
   ELSIF category IN ('OPERATION_STATE','CUSTODY_LOCATOR') THEN result:=result||jsonb_build_object(category,NULL);
   ELSE RAISE EXCEPTION 'INVALID_OUTPUT_CATEGORY'; END IF;
 END LOOP;
 RETURN jsonb_build_object('disposition','RESOLVED','outputs',result);
END $$;

CREATE FUNCTION jous_authority.original_attempt_admission(r jsonb) RETURNS jsonb LANGUAGE sql
SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT jous_authority.effect(r,'ORIGINAL_ATTEMPT_ADMISSION') $$;
CREATE FUNCTION jous_authority.dispatch_claim(r jsonb) RETURNS jsonb LANGUAGE sql
SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT jous_authority.effect(r,'DISPATCH_CLAIM') $$;
CREATE FUNCTION jous_authority.checkpoint_publication(r jsonb) RETURNS jsonb LANGUAGE sql
SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT jous_authority.effect(r,'CHECKPOINT_PUBLICATION') $$;
CREATE FUNCTION jous_authority.activation_cas(r jsonb) RETURNS jsonb LANGUAGE sql
SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT jous_authority.effect(r,'ACTIVATION_CAS') $$;
CREATE FUNCTION jous_authority.authoritative_readback(r jsonb) RETURNS jsonb LANGUAGE sql
SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT jous_authority.observe(r,'AUTHORITATIVE_READBACK') $$;
CREATE FUNCTION jous_authority.read_only_resolution(r jsonb) RETURNS jsonb LANGUAGE sql
SECURITY DEFINER SET search_path=pg_catalog AS $$ SELECT jous_authority.observe(r,'READ_ONLY_RESOLUTION') $$;

-- Internal append-only receipt/acknowledgement material, never admission, claim,
-- upload or effect entry. No public provider operation or retry is introduced.
CREATE FUNCTION jous_authority.append_material(r jsonb,m jsonb) RETURNS void LANGUAGE plpgsql
SECURITY DEFINER SET search_path=pg_catalog AS $$
DECLARE names text[]:=ARRAY['namespace','incarnation_id','material_id','evidence_identity','parent_kind',
 'subject_kind','subject_id','sequence','activation_operation_id','request_id','receipt_role',
 'original_raw','raw_sha256','issuer_id','authentication_ref','subject_ref'];
 h jous_authority.history; body jsonb; env jsonb; expected_role text; parent_request jsonb;
BEGIN
 -- Check actual session membership, not caller JSON or SECURITY DEFINER owner.
 -- An observer-only (or incompatible mixed) identity cannot enter this path.
 IF pg_has_role(session_user,'jous_observer','MEMBER') THEN RAISE EXCEPTION 'MATERIAL_OBSERVER_FORBIDDEN'; END IF;
 IF r->>'operation'='EVIDENCE_CUSTODY_BINDING' THEN
   IF NOT pg_has_role(session_user,'jous_custody','MEMBER') THEN RAISE EXCEPTION 'MATERIAL_CUSTODY_SCOPE'; END IF;
 ELSE
   IF NOT pg_has_role(session_user,'jous_broker','MEMBER') THEN RAISE EXCEPTION 'MATERIAL_BROKER_SCOPE'; END IF;
 END IF;
 PERFORM jous_authority.check_request(r,r->>'operation');
 PERFORM jous_authority.check_authority(r);
 IF jsonb_typeof(m)<>'object' OR NOT(m ?& names) OR (m-names)<>'{}'::jsonb THEN
   RAISE EXCEPTION 'CLOSED_MATERIAL_SCHEMA'; END IF;
 IF m->>'original_raw' !~ '^([0-9a-f]{2})*$' OR length(m->>'original_raw')>16777216
    OR m->>'raw_sha256' !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'MATERIAL_BYTES_DOMAIN'; END IF;

 IF (m->>'namespace',m->>'incarnation_id',m->>'request_id') IS DISTINCT FROM
    (r->>'namespace',r->>'incarnation_id',r->>'request_id') THEN RAISE EXCEPTION 'MATERIAL_CALLER_SCOPE'; END IF;
 -- The envelope/body are the existing exact-byte codec. Parsing below only
 -- validates association; it never normalizes bytes or substitutes for KMS
 -- authentication performed by the independently qualified internal issuer.
 env:=convert_from(decode(m->>'original_raw','hex'),'UTF8')::jsonb;
 body:=convert_from(decode(translate(env->>'body','-_','+/') ||
             repeat('=',(4-length(env->>'body')%4)%4),'base64'),'UTF8')::jsonb;
 IF encode(sha256(decode(m->>'original_raw','hex')),'hex') IS DISTINCT FROM m->>'raw_sha256'
    OR m->'authentication_ref' IS DISTINCT FROM jsonb_build_object('identity',m->>'material_id','sha256',m->>'raw_sha256')
    OR m->>'material_id' IS DISTINCT FROM m->>'evidence_identity'
    OR body->>'receipt_id' IS DISTINCT FROM m->>'material_id'
    OR body->>'receipt_role' IS DISTINCT FROM m->>'receipt_role'
    OR body->>'issuer_id' IS DISTINCT FROM m->>'issuer_id'
    OR body->'subject_ref' IS DISTINCT FROM m->'subject_ref'
    OR body->>'namespace' IS DISTINCT FROM r->>'namespace'
    OR body->>'incarnation_id' IS DISTINCT FROM r->>'incarnation_id'
    OR body->'configuration_ref' IS DISTINCT FROM r->'configuration_ref'
    OR body->>'request_id' IS DISTINCT FROM r->>'request_id'
    OR body->>'outcome' IS DISTINCT FROM 'ESTABLISHED' THEN RAISE EXCEPTION 'MATERIAL_SIGNED_SCOPE'; END IF;
 expected_role:=CASE r->>'operation'
   WHEN 'ORIGINAL_ATTEMPT_ADMISSION' THEN 'ENTRY_' || CASE r->>'operation_role' WHEN 'CHECKPOINT_PUBLICATION' THEN 'PUBLICATION' ELSE 'CAS' END
   WHEN 'DISPATCH_CLAIM' THEN 'CLAIM_' || CASE r->>'operation_role' WHEN 'CHECKPOINT_PUBLICATION' THEN 'PUBLICATION' ELSE 'CAS' END
   WHEN 'CHECKPOINT_PUBLICATION' THEN 'RESULT_PUBLICATION'
   WHEN 'ACTIVATION_CAS' THEN 'RESULT_CAS'
   WHEN 'AUTHORITATIVE_READBACK' THEN 'READBACK'
   WHEN 'EVIDENCE_CUSTODY_BINDING' THEN CASE r->>'phase' WHEN 'RESERVE' THEN 'CUSTODY_RESERVE' WHEN 'BIND' THEN 'CUSTODY_BIND' END END;
 IF expected_role IS NULL OR m->>'receipt_role' IS DISTINCT FROM expected_role THEN RAISE EXCEPTION 'MATERIAL_ROLE'; END IF;
 IF expected_role='READBACK' THEN
   IF m->>'parent_kind' IS DISTINCT FROM 'READBACK' OR m->>'activation_operation_id' IS DISTINCT FROM r->>'operation_id'
      OR NOT EXISTS(SELECT 1 FROM jous_authority.activation a WHERE a.namespace=r->>'namespace'
       AND a.incarnation_id=r->>'incarnation_id' AND a.operation_id=r->>'operation_id'
       AND a.lifecycle_binding=jous_authority.lifecycle_of(r) AND a.decision='ACTIVATED'
       AND a.payload_sha256=decode(r->>'payload_sha256','hex')) THEN RAISE EXCEPTION 'MATERIAL_READBACK_PARENT'; END IF;
 ELSE
   SELECT * INTO STRICT h FROM jous_authority.history WHERE namespace=m->>'namespace'
      AND incarnation_id=m->>'incarnation_id' AND subject_kind=m->>'subject_kind'
      AND subject_id=m->>'subject_id' AND sequence=(m->>'sequence')::bigint;
   parent_request:=(convert_from(h.decision_raw,'UTF8')::jsonb)->'request';
   IF m->>'parent_kind' IS DISTINCT FROM 'DECISION' OR m->'subject_ref' IS DISTINCT FROM h.decision_ref
      OR parent_request->>'request_id' IS DISTINCT FROM r->>'request_id'
      OR parent_request->>'principal_id' IS DISTINCT FROM r->>'principal_id'
      OR parent_request->>'credential_identity' IS DISTINCT FROM r->>'credential_identity'
      OR parent_request->>'logical_role' IS DISTINCT FROM r->>'logical_role'
      OR parent_request->'authorization_ref' IS DISTINCT FROM r->'authorization_ref'
      OR h.subject_id IS DISTINCT FROM COALESCE(r->>'operation_id',r->>'evidence_identity')
      OR h.subject_kind IS DISTINCT FROM CASE WHEN r->>'operation'='EVIDENCE_CUSTODY_BINDING' THEN 'CUSTODY' ELSE 'OPERATION' END
      OR h.decision IS DISTINCT FROM CASE r->>'operation' WHEN 'ORIGINAL_ATTEMPT_ADMISSION' THEN 'ADMITTED'
       WHEN 'DISPATCH_CLAIM' THEN 'CLAIMED' WHEN 'CHECKPOINT_PUBLICATION' THEN 'CHECKPOINT_PUBLISHED'
       WHEN 'ACTIVATION_CAS' THEN 'ACTIVATED' WHEN 'EVIDENCE_CUSTODY_BINDING' THEN
       CASE r->>'phase' WHEN 'RESERVE' THEN 'CUSTODY_RESERVED' WHEN 'BIND' THEN 'CUSTODY_BOUND' END END
      THEN RAISE EXCEPTION 'MATERIAL_DECISION_PARENT'; END IF;
 END IF;
 INSERT INTO jous_authority.material VALUES(m->>'namespace',m->>'incarnation_id',m->>'material_id',
  m->>'evidence_identity',m->>'parent_kind',m->>'subject_kind',m->>'subject_id',(m->>'sequence')::bigint,
  m->>'activation_operation_id',m->>'request_id',m->>'receipt_role',decode(m->>'original_raw','hex'),
  decode(m->>'raw_sha256','hex'),m->>'issuer_id',m->'authentication_ref',m->'subject_ref');
END $$;

-- Non-login owners and only exact EXECUTE grants. No login, credential, role
-- membership, schema bootstrap or incarnation adoption is supplied here.
ALTER TABLE jous_authority.incarnation OWNER TO jous_table_owner;
ALTER TABLE jous_authority.slot OWNER TO jous_table_owner;
ALTER TABLE jous_authority.lifecycle OWNER TO jous_table_owner;
ALTER TABLE jous_authority.admission OWNER TO jous_table_owner;
ALTER TABLE jous_authority.claim OWNER TO jous_table_owner;
ALTER TABLE jous_authority.publication OWNER TO jous_table_owner;
ALTER TABLE jous_authority.activation OWNER TO jous_table_owner;
ALTER TABLE jous_authority.history OWNER TO jous_table_owner;
ALTER TABLE jous_authority.material OWNER TO jous_table_owner;
ALTER TABLE jous_authority.locator OWNER TO jous_table_owner;
GRANT SELECT ON ALL TABLES IN SCHEMA jous_authority TO jous_observe_owner;
GRANT SELECT ON jous_authority.incarnation TO jous_effect_owner,jous_custody_owner;
GRANT SELECT,UPDATE ON jous_authority.slot,jous_authority.lifecycle TO jous_effect_owner;
GRANT INSERT ON jous_authority.lifecycle TO jous_effect_owner;
GRANT SELECT,INSERT ON jous_authority.admission,jous_authority.claim,jous_authority.publication,
    jous_authority.activation,jous_authority.history,jous_authority.material TO jous_effect_owner;
GRANT SELECT,INSERT,UPDATE ON jous_authority.locator TO jous_custody_owner;
GRANT SELECT,INSERT ON jous_authority.history,jous_authority.material TO jous_custody_owner;
GRANT SELECT ON jous_authority.activation TO jous_custody_owner;
GRANT EXECUTE ON FUNCTION jous_authority.lifecycle_of(jsonb) TO jous_custody_owner;
ALTER FUNCTION jous_authority.effect(jsonb,text) OWNER TO jous_effect_owner;
ALTER FUNCTION jous_authority.immutable() OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.transition_guard() OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.history_role_guard() OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.lifecycle_of(jsonb) OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.original_of(jsonb) OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.reject(text) OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.check_request(jsonb,text) OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.check_authority(jsonb) OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.append_history(jsonb,text,text,bigint,text) OWNER TO jous_table_owner;
ALTER FUNCTION jous_authority.original_attempt_admission(jsonb) OWNER TO jous_effect_owner;
ALTER FUNCTION jous_authority.dispatch_claim(jsonb) OWNER TO jous_effect_owner;
ALTER FUNCTION jous_authority.checkpoint_publication(jsonb) OWNER TO jous_effect_owner;
ALTER FUNCTION jous_authority.activation_cas(jsonb) OWNER TO jous_effect_owner;
ALTER FUNCTION jous_authority.custody_binding(jsonb) OWNER TO jous_custody_owner;
ALTER FUNCTION jous_authority.append_material(jsonb,jsonb) OWNER TO jous_custody_owner;
ALTER FUNCTION jous_authority.observe(jsonb,text) OWNER TO jous_observe_owner;
ALTER FUNCTION jous_authority.authoritative_readback(jsonb) OWNER TO jous_observe_owner;
ALTER FUNCTION jous_authority.read_only_resolution(jsonb) OWNER TO jous_observe_owner;
REVOKE ALL ON ALL TABLES IN SCHEMA jous_authority FROM PUBLIC,jous_broker,jous_custody,jous_observer;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA jous_authority FROM PUBLIC;
GRANT EXECUTE ON FUNCTION jous_authority.lifecycle_of(jsonb),jous_authority.original_of(jsonb),
 jous_authority.reject(text),jous_authority.check_authority(jsonb),
 jous_authority.append_history(jsonb,text,text,bigint,text) TO jous_effect_owner,jous_custody_owner;
GRANT EXECUTE ON FUNCTION jous_authority.check_request(jsonb,text) TO jous_effect_owner,jous_custody_owner,jous_observe_owner;
GRANT EXECUTE ON FUNCTION jous_authority.lifecycle_of(jsonb),jous_authority.reject(text),
 jous_authority.check_authority(jsonb) TO jous_observe_owner;
GRANT EXECUTE ON FUNCTION jous_authority.original_attempt_admission(jsonb),
 jous_authority.dispatch_claim(jsonb),jous_authority.checkpoint_publication(jsonb),
 jous_authority.activation_cas(jsonb) TO jous_broker;
GRANT EXECUTE ON FUNCTION jous_authority.custody_binding(jsonb) TO jous_custody;
GRANT EXECUTE ON FUNCTION jous_authority.append_material(jsonb,jsonb) TO jous_broker,jous_custody;
GRANT EXECUTE ON FUNCTION jous_authority.authoritative_readback(jsonb),
 jous_authority.read_only_resolution(jsonb) TO jous_observer;
GRANT EXECUTE ON FUNCTION jous_authority.read_only_resolution(jsonb) TO jous_custody;
COMMIT;
