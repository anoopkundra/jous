"""Closed offline-approved Step 7 contracts. Never connect, mutate, or learn trees."""
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from weakref import WeakKeyDictionary

ROOT = Path(__file__).resolve().parents[4]
M1_PATH = 'services/api/infrastructure/step7_operator514_amendment.json'
POLICY_PATH = 'services/api/infrastructure/step7_policy_template_contract.json'
M1_SHA = '10264e9561a030e4a36b3efa4dc4ccc6eacec5632f6b9dcef7825398de4bc545'
POLICY_SHA = '1d212a755e951be68094981e97486c8cbf10d8c28bf8d845e9b252f183391648'
BASE_SHA = '60efef97d11e85a0be679a32f5aa3163f35017f4bebf8d6120bdb183731734e0'
AUTHORIZE_SHA = 'ad494861a54cb78afa1235fa661a046e2ed182605b7bb6295579968be22497f3'
MANAGED_SHA = '922b335f605d9f96b14791bdb2d4896d2c55f43e7ad0f0116417c54a2826ee79'
HISTORICAL_SHA = '9b8ccd7f791134ff51f299d930b2c8678cd21f19160e582791d296fa442009e5'
OPERATOR_SQL_SHA = 'c2834fafc2a98d08805ede9c1fb2332a607977895c0654996487717e2d218256'
_issued = WeakKeyDictionary()

class ContractRejected(ValueError):
    pass

def require(ok, gate):
    if not ok:
        raise ContractRejected(gate)

def canonical(value):
    def check(v):
        require(v is None or type(v) in (str,int,bool,list,dict), 'CONTRACT_VALUE_TYPE')
        if type(v) is dict:
            require(all(type(k) is str for k in v), 'CONTRACT_KEY_TYPE')
            for child in v.values(): check(child)
        elif type(v) is list:
            for child in v: check(child)
    check(value)
    return json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,
                      allow_nan=False).encode('utf-8')

def parse(raw):
    def pairs(items):
        result={}
        for k,v in items:
            require(k not in result,'CONTRACT_DUPLICATE_KEY'); result[k]=v
        return result
    require(type(raw) is bytes and len(raw)<=1000000,'CONTRACT_SIZE')
    try:
        data=json.loads(raw,object_pairs_hook=pairs,
                        parse_constant=lambda _: (_ for _ in ()).throw(ContractRejected('CONTRACT_NONFINITE')))
        canonical(data)
        return data
    except (UnicodeError,json.JSONDecodeError):
        raise ContractRejected('CONTRACT_JSON') from None

def load(path, sha):
    p=ROOT/path
    require(p.is_file() and not p.is_symlink(),'CONTRACT_PATH')
    raw=p.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==sha,'CONTRACT_HASH')
    return parse(raw)

def exact(a,b,gate):
    require(canonical(a)==canonical(b),gate)

def oid(v):
    return type(v) is int and 0<v<=4294967295

@dataclass(frozen=True,eq=False)
class ApprovedFinalContract:
    payload: bytes
@dataclass(frozen=True,eq=False)
class VerifiedExistingBindings:
    payload: bytes
@dataclass(frozen=True,eq=False)
class VerifiedCreatedBindings:
    payload: bytes
@dataclass(frozen=True,eq=False)
class ExpectedPolicySet:
    payload: bytes
@dataclass(frozen=True,eq=False)
class ObservedPolicySet:
    payload: bytes
@dataclass(frozen=True,eq=False)
class VerifiedPolicyContinuity:
    payload: bytes

def _issue(cls, value):
    obj=cls(canonical(value)); _issued[obj]=obj.payload; return obj

def _read(obj, cls):
    require(type(obj) is cls and _issued.get(obj) == obj.payload,'BINDING_TRUST_TYPE')
    return parse(obj.payload)

def apply_m1(base):
    amendment=load(M1_PATH,M1_SHA)
    expected_keys={'schema','base_manifest_sha256','evidence_sha256','observation',
                   'base_operator','add_fields','migration_execution_approved','runtime_activation_approved'}
    require(set(amendment)==expected_keys,'M1_SCHEMA')
    exact({k:amendment[k] for k in expected_keys-{'base_operator'}},dict(
        schema='jous.step7.operator514-amendment.v1',base_manifest_sha256=BASE_SHA,
        evidence_sha256=MANAGED_SHA,observation=dict(sql_sha256=OPERATOR_SQL_SHA,
        parameters={'ids':[514]},operator_oid=514),add_fields=dict(oprcanmerge=False,oprcanhash=False),
        migration_execution_approved=False,runtime_activation_approved=False),'M1_LINKAGE')
    operators=base['referent_bindings']['operators']
    require(len(operators)==1 and operators[0].get('oid')==514,'M1_OPERATOR')
    exact(operators[0],amendment['base_operator'],'M1_BASE_OPERATOR')
    require('oprcanmerge' not in operators[0] and 'oprcanhash' not in operators[0],'M1_OVERWRITE')
    result=parse(canonical(base))
    result['referent_bindings']['operators'][0]['oprcanmerge']=False
    result['referent_bindings']['operators'][0]['oprcanhash']=False
    return result

def load_final_contract():
    data=load(POLICY_PATH,POLICY_SHA)
    require(set(data)=={'schema','parents','evidence','migrations','target','templates','policies',
        'numeric_audit','builtins','relations','helpers','created_schema','io','bitmap','provenance',
        'policy_oid_rule','two_pass','slot_bindings','null_positions','migration_execution_approved','runtime_activation_approved'},'POLICY_CONTRACT_SCHEMA')
    exact(data['parents'],dict(base=BASE_SHA,authorize=AUTHORIZE_SHA,m1=M1_SHA),'CONTRACT_PARENT')
    exact(data['evidence'],dict(managed=MANAGED_SHA,historical=HISTORICAL_SHA),'CONTRACT_EVIDENCE')
    exact(data['migrations'],{'0001':'a78d9035cc39f1c5030b6ae436506d9d5ae3c978',
         '0002':'cae08d9cf548480fb5d064becca1e89ca2dd898b'},'CONTRACT_MIGRATION')
    require(data['schema']=='jous.step7.policy-template-contract.v1' and
            data['migration_execution_approved'] is False and data['runtime_activation_approved'] is False,
            'CONTRACT_APPROVAL')
    require(set(data['builtins'])=={'types','functions','operators','collations'},'BUILTIN_REFERENT_MISSING')
    validate_builtin_domains(data['builtins'])
    require(len(data['templates'])==19 and len(data['policies'])==13 and
        sum(len(t['slots']) for t in data['templates'])==31,'POLICY_TEMPLATE_MISMATCH')
    exact(data['bitmap'],dict(first_low_invalid=-7,offset=7,selected_columns={
        'users':['id','status'],'organization_memberships':['organization_id'],'organizations':['id']}),
        'PERMISSION_BITMAP_MISMATCH')
    exact(data['io'],dict(source_type=25,output_function=47,intermediate_type=2275,
        input_function=2952,destination_type=2950,io_parameter=2950,output_typmod=-1,
        source_collation=100,result_collation=0),'TYPE_IO_LINKAGE_MISMATCH')
    types={t['oid']:t for t in data['builtins']['types']}
    functions={p['oid']:p for p in data['builtins']['functions']}
    require(types[25]['typoutput']==47 and types[2950]['typinput']==2952 and
        types[2950]['typelem']==0 and types[2275]['typname']=='cstring' and
        functions[47]['input_oids']==[25] and functions[47]['prorettype']==2275 and
        functions[2952]['input_oids']==[2275] and functions[2952]['prorettype']==2950,
        'TYPE_IO_LINKAGE_MISMATCH')
    validate_templates(data)
    return _issue(ApprovedFinalContract,data)

def validate_templates(data):
    seen=set()
    slots_seen={}
    texts=[]
    for t in data['templates']:
        require(set(t)=={'policy','clause','golden_raw','golden_sha256','golden_byte_length',
          'fixture2_sha256','fixture2_byte_length','exact_reproduction','slots'},'POLICY_TEMPLATE_MISMATCH')
        key=t['policy']+'.'+t['clause'];require(key not in seen,'POLICY_TEMPLATE_MISMATCH');seen.add(key)
        texts.append(t['golden_raw'])
        raw=t['golden_raw'].encode('utf-8')
        require(len(raw)==t['golden_byte_length'] and hashlib.sha256(raw).hexdigest()==t['golden_sha256'],
                'POLICY_TEMPLATE_MISMATCH')
        last=0
        for s in sorted(t['slots'],key=lambda s:s['offset']):
            start=s['offset'];length=s['length']
            require(type(start) is int and type(length) is int and start>=last and length>0 and
                    start+length<=len(raw),'POLICY_TEMPLATE_MISMATCH')
            require(s['binding'] in {'relation:users','relation:organizations',
                'relation:organization_memberships','helper:organization_is_active'} and
                s['policy']==t['policy'] and s['clause']==t['clause'],'POLICY_BINDING_MISMATCH')
            before=s['context_before'].encode();after=s['context_after'].encode()
            require(raw[start:start+length]==s['original_decimal'].encode() and
                raw[:start].endswith(before) and raw[start+length:].startswith(after) and
                raw[start-1:start]==b' ' and raw[start+length:start+length+1]==b' ' and
                re.fullmatch(b'[0-9]+',raw[start:start+length]) is not None,'POLICY_TEMPLATE_MISMATCH')
            slots_seen[s['binding']]=slots_seen.get(s['binding'],0)+1
            last=start+length
    exact(slots_seen,data['slot_bindings'],'POLICY_TEMPLATE_MISMATCH')
    nulls=[dict(policy=p['relation_binding'].split(':',1)[1]+'.'+p['policy_name'],clause=clause)
        for p in data['policies'] for field,clause in [('qual_template','qual'),('with_check_template','with_check')]
        if p[field] is None]
    exact(nulls,data['null_positions'],'POLICY_TEMPLATE_MISMATCH')
    require(len(nulls)==7,'POLICY_TEMPLATE_MISMATCH')
    for name,alias,count in [('users','u',3),('organization_memberships','m',5),('organizations','o',6)]:
        relation=next(r for r in data['relations'] if r['name']==name)
        names=' '.join('"'+a['attname']+'"' for a in relation['columns'])
        eref=':eref {ALIAS :aliasname '+alias+' :colnames ('+names+')}'
        require(sum(t.count(eref) for t in texts)==count,'RTE_LAYOUT_MISMATCH')
        numbers=[next(a['attnum'] for a in relation['columns'] if a['attname']==col)+7
                 for col in data['bitmap']['selected_columns'][name]]
        bitmap=':selectedCols (b '+' '.join(map(str,numbers))+')'
        require(sum(t.count(bitmap) for t in texts)==count,'PERMISSION_BITMAP_MISMATCH')
    expected={p['qual_template'] for p in data['policies']}|{p['with_check_template'] for p in data['policies']}
    require(seen==expected-{None},'POLICY_TEMPLATE_MISMATCH')

TYPE_SQL="""SELECT t.oid,n.nspname AS schema,t.typname,t.typnamespace,t.typtype::text AS typtype,
 t.typcategory::text AS typcategory,t.typlen,t.typbyval,t.typalign::text AS typalign,
 t.typstorage::text AS typstorage,t.typelem,t.typarray,t.typcollation,
 t.typinput::oid AS typinput,t.typoutput::oid AS typoutput,t.typbasetype,t.typrelid,t.typowner,r.rolname AS owner
 FROM pg_catalog.pg_type t JOIN pg_catalog.pg_namespace n ON n.oid=t.typnamespace JOIN pg_catalog.pg_roles r ON r.oid=t.typowner WHERE t.oid=ANY(:ids)"""
FUNCTION_SQL="""SELECT p.oid,n.nspname AS schema,p.proname,p.pronamespace,p.prolang,l.lanname AS language,
 p.prokind::text AS prokind,p.prosecdef,p.provolatile::text AS provolatile,p.proparallel::text AS proparallel,
 p.proisstrict,p.proleakproof,p.proretset,p.prorettype,p.provariadic,p.pronargdefaults,
 p.proowner,r.rolname AS owner,p.prosupport::oid AS prosupport,p.proconfig,p.probin,p.prosrc,p.proargtypes::oid[] AS input_oids,
 p.proargdefaults IS NULL AS no_defaults,p.prosqlbody IS NULL AS no_sql_body
 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
 JOIN pg_catalog.pg_language l ON l.oid=p.prolang JOIN pg_catalog.pg_roles r ON r.oid=p.proowner WHERE p.oid=ANY(:ids)"""
OPERATOR_SQL="""SELECT o.oid,n.nspname AS schema,o.oprname,o.oprnamespace,o.oprkind::text AS oprkind,
 o.oprcanmerge,o.oprcanhash,o.oprleft,o.oprright,o.oprresult,o.oprcom,o.oprnegate,
 o.oprowner,r.rolname AS owner,o.oprcode::oid AS oprcode,o.oprrest::oid AS oprrest,o.oprjoin::oid AS oprjoin
 FROM pg_catalog.pg_operator o JOIN pg_catalog.pg_namespace n ON n.oid=o.oprnamespace JOIN pg_catalog.pg_roles r ON r.oid=o.oprowner WHERE o.oid=ANY(:ids)"""
COLLATION_SQL="""SELECT c.oid,n.nspname AS schema,n.oid AS namespace_oid,c.collname,
 c.collprovider::text AS collprovider,c.collisdeterministic,c.collencoding,c.collcollate,c.collctype,
 c.colllocale,c.collicurules,c.collversion,c.collowner,r.rolname AS owner FROM pg_catalog.pg_collation c
 JOIN pg_catalog.pg_namespace n ON n.oid=c.collnamespace JOIN pg_catalog.pg_roles r ON r.oid=c.collowner WHERE c.oid=ANY(:ids)"""
RELATION_SQL="""SELECT c.oid,n.oid AS namespace_oid,n.nspname AS schema,c.relname AS name,
 c.relkind::text AS relkind,c.relpersistence::text AS relpersistence,r.rolname AS owner,c.relowner AS owner_oid,
 c.relispartition,c.relrowsecurity,c.relforcerowsecurity,
 EXISTS(SELECT 1 FROM pg_catalog.pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid) AS inheritance
 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_roles r ON r.oid=c.relowner
 WHERE n.nspname='public' AND c.relname IN ('users','organizations','organization_memberships','projects')"""
COLUMN_SQL="""SELECT a.attrelid,a.attnum,a.attname,a.atttypid,a.atttypmod,a.attcollation,a.attnotnull,
 a.attisdropped,a.attidentity::text AS attidentity,a.attgenerated::text AS attgenerated,
 EXISTS(SELECT 1 FROM pg_catalog.pg_attrdef d WHERE d.adrelid=a.attrelid AND d.adnum=a.attnum) AS has_default
 FROM pg_catalog.pg_attribute a WHERE a.attrelid=ANY(:ids) AND a.attnum>0 ORDER BY a.attrelid,a.attnum"""
ROLE_SQL="SELECT oid,rolname FROM pg_catalog.pg_roles WHERE rolname IN ('postgres','jous_runtime','jous_security_reader')"
TARGET_SQL="""SELECT d.oid,d.datname,d.encoding,d.datlocprovider::text AS datlocprovider,
 d.datcollate,d.datctype,d.datlocale,d.daticurules,d.datcollversion,
 current_setting('server_version') AS server_version,current_setting('server_version_num')::integer AS server_version_num
 FROM pg_catalog.pg_database d WHERE d.datname=current_database()"""

def validate_builtin_domains(builtins):
    """Expected catalog domains are validated before any credential acquisition.
    No token-spelling coercion: catalog chars, booleans and integers are distinct.
    """
    domains={
        'types':({'typbyval'}, {'typtype':'bcdeprm','typcategory':'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                  'typalign':'csid','typstorage':'pexm'},
                 {'oid','typnamespace','typlen','typelem','typarray','typcollation','typinput',
                  'typoutput','typbasetype','typrelid','typowner'}),
        'functions':({'prosecdef','proisstrict','proleakproof','proretset','no_defaults','no_sql_body'},
                     {'prokind':'f','provolatile':'ivs','proparallel':'urs'},
                     {'oid','pronamespace','prolang','prorettype','provariadic','pronargdefaults','prosupport','proowner'}),
        'operators':({'oprcanmerge','oprcanhash'}, {'oprkind':'blr'},
                     {'oid','oprnamespace','oprleft','oprright','oprresult','oprcom','oprnegate','oprcode','oprrest','oprjoin','oprowner'}),
        'collations':({'collisdeterministic'}, {'collprovider':'d'}, {'oid','namespace_oid','collencoding','collowner'})}
    for kind,(booleans,chars,integers) in domains.items():
        require(type(builtins.get(kind)) is list and bool(builtins[kind]),'BUILTIN_EXPECTED_DOMAIN')
        ownerfield={'types':'typowner','functions':'proowner','operators':'oprowner','collations':'collowner'}[kind]
        for row in builtins[kind]:
            require(type(row) is dict,'BUILTIN_EXPECTED_DOMAIN')
            for key in booleans:
                require(type(row.get(key)) is bool,'BUILTIN_EXPECTED_DOMAIN')
            for key,allowed in chars.items():
                value=row.get(key)
                require(type(value) is str and len(value)==1 and value in allowed,'BUILTIN_EXPECTED_DOMAIN')
            for key in integers:
                require(type(row.get(key)) is int,'BUILTIN_EXPECTED_DOMAIN')
            require(row.get(ownerfield)==10 and row.get('owner')=='supabase_admin','BUILTIN_EXPECTED_OWNER')
            if kind=='functions':
                require(type(row.get('input_oids')) is list and all(oid(v) for v in row['input_oids']),
                        'BUILTIN_EXPECTED_DOMAIN')
            if kind=='types':
                require(row['typlen'] in (-2,-1,1,2,4,8,16),'BUILTIN_EXPECTED_DOMAIN')
                if row['oid']==2281:
                    require(row['typlen']==8 and row['typalign']=='d','BUILTIN_EXPECTED_DOMAIN')

def _multiset(actual,expected):
    return sorted(canonical(x) for x in actual)==sorted(canonical(x) for x in expected)

def verify_builtins(actual, expected):
    require(set(actual)==set(expected),'BUILTIN_REFERENT_MISSING')
    for kind in expected:
        rows=actual[kind];wanted=expected[kind]; ids=[x.get('oid') for x in rows]
        require(all(oid(x) for x in ids),'BUILTIN_REFERENT_MISMATCH')
        require(len(ids)==len(set(ids)),'BUILTIN_REFERENT_DUPLICATE')
        require(set(ids)<=set(x['oid'] for x in wanted),'BUILTIN_REFERENT_UNEXPECTED')
        require(set(ids)==set(x['oid'] for x in wanted),'BUILTIN_REFERENT_MISSING')
        if kind=='types':
            a={x['oid']:x for x in rows};e={x['oid']:x for x in wanted}
            for i in a:
                exact([a[i].get('typinput'),a[i].get('typoutput')],
                      [e[i]['typinput'],e[i]['typoutput']],'TYPE_IO_LINKAGE_MISMATCH')
        require(_multiset(rows,wanted),'BUILTIN_REFERENT_MISMATCH')

def _existing(connection, contract, query, migrated):
    c=_read(contract,ApprovedFinalContract)
    target=query(connection,TARGET_SQL)
    require(len(target)==1,'TARGET_CONTEXT_MISMATCH')
    target=target[0];expected=dict(c['target']['database'],server_version='17.11',server_version_num=170011)
    exact(target,expected,'TARGET_CONTEXT_MISMATCH')
    roles=query(connection,ROLE_SQL)
    require(len(roles)==3 and len({r['rolname'] for r in roles})==3 and
        all(oid(r['oid']) for r in roles) and len({r['oid'] for r in roles})==3,'POLICY_BINDING_MISMATCH')
    rolemap={r['rolname']:r['oid'] for r in roles}
    require(set(rolemap)=={'postgres','jous_runtime','jous_security_reader'},'POLICY_BINDING_MISMATCH')
    builtins={k:query(connection,sql,{'ids':[r['oid'] for r in c['builtins'][k]]}) for k,sql in
        [('types',TYPE_SQL),('functions',FUNCTION_SQL),('operators',OPERATOR_SQL),('collations',COLLATION_SQL)]}
    verify_builtins(builtins,c['builtins'])
    builtins={k:sorted(v,key=lambda r:r['oid']) for k,v in builtins.items()}
    relations=query(connection,RELATION_SQL)
    require(len(relations)==4 and len({r['name'] for r in relations})==4 and
        len({r['oid'] for r in relations})==4,'RELATION_BINDING_MISMATCH')
    columns=query(connection,COLUMN_SQL,{'ids':[r['oid'] for r in relations]})
    snapshots=[]
    for e in c['relations']:
        choices=[r for r in relations if r['name']==e['name']];require(len(choices)==1,'RELATION_BINDING_MISMATCH')
        r=choices[0]
        require(oid(r['oid']) and r['namespace_oid']==2200 and r['owner_oid']==rolemap['postgres'],
                'RELATION_BINDING_MISMATCH')
        for k in ('schema','name','relkind','relpersistence','owner','relispartition'):
            exact(r[k],e[k],'RELATION_LAYOUT_MISMATCH')
        require(r['inheritance'] is False,'RELATION_TOPOLOGY_MISMATCH')
        require(r['relrowsecurity'] is True and r['relforcerowsecurity'] is migrated,'TABLE_RLS')
        cols=[{k:v for k,v in a.items() if k!='attrelid'} for a in columns if a['attrelid']==r['oid']]
        require(len(cols)==len(e['columns']),'COLUMN_BINDING_MISMATCH')
        require(all(a['attisdropped'] is False for a in cols),'COLUMN_DROPPED_STATE_MISMATCH')
        require([a['attnum'] for a in cols]==list(range(1,len(cols)+1)), 'COLUMN_ORDER_MISMATCH')
        for a,w in zip(cols,e['columns']):
            for field,gate in [('attname','COLUMN_ORDER_MISMATCH'),('atttypid','COLUMN_TYPE_MISMATCH'),
                ('atttypmod','COLUMN_TYPMOD_MISMATCH'),('attcollation','COLUMN_COLLATION_MISMATCH'),
                ('attidentity','COLUMN_GENERATION_MISMATCH'),('attgenerated','COLUMN_GENERATION_MISMATCH')]:
                exact(a[field],w[field],gate)
            exact(a,w,'RELATION_LAYOUT_MISMATCH')
        stable=dict(r);stable.pop('relforcerowsecurity');stable['columns']=cols;snapshots.append(stable)
    require(len(columns)==sum(len(r['columns']) for r in snapshots),'COLUMN_BINDING_MISMATCH')
    return dict(contract=POLICY_SHA,target=target,roles=rolemap,builtins=builtins,
                relations=sorted(snapshots,key=lambda x:x['name']))

def freeze_pre_migration_bindings(connection,contract,query):
    return _issue(VerifiedExistingBindings,_existing(connection,contract,query,False))

def revalidate_existing_bindings(connection,contract,bindings,query):
    expected=_read(bindings,VerifiedExistingBindings)
    actual=_existing(connection,contract,query,True)
    exact(actual,expected,'RELATION_BINDING_MISMATCH')

CREATED_SQL="""SELECT p.oid,n.oid AS namespace_oid,n.nspname AS schema,n.nspowner,
 nr.rolname AS namespace_owner,p.proname,p.proowner,p.prolang,l.lanname AS language,
 p.proargtypes::oid[] AS args,p.prorettype AS returns,p.proargnames,p.proargmodes,p.proallargtypes,
 p.prokind::text AS prokind,p.prosecdef,p.provolatile::text AS provolatile,
 p.proparallel::text AS proparallel,p.proisstrict,p.proleakproof,p.proretset,p.provariadic,
 p.pronargdefaults,p.proargdefaults IS NULL AS no_defaults,p.prosqlbody IS NULL AS text_body,
 p.proconfig,p.probin,p.prosrc FROM pg_catalog.pg_proc p
 JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
 JOIN pg_catalog.pg_roles nr ON nr.oid=n.nspowner JOIN pg_catalog.pg_language l ON l.oid=p.prolang
 WHERE n.nspname='jous_security'"""

CREATED_ACL_SQL="""SELECT p.proname,a.grantor,a.grantee,a.privilege_type,a.is_grantable
 FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace,
 LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
 WHERE n.nspname='jous_security'"""
CREATED_SCHEMA_ACL_SQL="""SELECT a.grantee,a.privilege_type,a.is_grantable FROM pg_catalog.pg_namespace n,
 LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
 WHERE n.nspname='jous_security' AND a.grantee<>n.nspowner"""

def verify_created_security_objects(connection,contract,existing,query):
    c=_read(contract,ApprovedFinalContract);b=_read(existing,VerifiedExistingBindings)
    rows=query(connection,CREATED_SQL)
    require(len(rows)==2 and len({r['oid'] for r in rows})==2 and
            len({r['namespace_oid'] for r in rows})==1,'POLICY_BINDING_MISMATCH')
    for h in c['helpers']:
        choices=[r for r in rows if r['proname']==h['name']];require(len(choices)==1,'POLICY_BINDING_MISMATCH')
        r=choices[0]
        expected=dict(schema='jous_security',namespace_owner='postgres',nspowner=b['roles']['postgres'],
            proname=h['name'],proowner=b['roles']['jous_security_reader'],prolang=14,language='sql',
            args=h['args'],returns=h['returns'],proargnames=h['argnames'],proargmodes=None,proallargtypes=None,
            prokind='f',prosecdef=True,provolatile='s',proparallel='u',proisstrict=False,proleakproof=False,
            proretset=False,provariadic=0,pronargdefaults=0,no_defaults=True,text_body=True,
            proconfig=['search_path=pg_catalog, pg_temp'],probin=None)
        exact({k:v for k,v in r.items() if k not in ('oid','namespace_oid','prosrc')},expected,'POLICY_BINDING_MISMATCH')
        require(oid(r['oid']) and oid(r['namespace_oid']) and type(r['prosrc']) is str and
            hashlib.sha256(r['prosrc'].encode()).hexdigest()==h['body_sha256'],'POLICY_BINDING_MISMATCH')
    acl=query(connection,CREATED_ACL_SQL)
    expected_acl=[dict(proname=h['name'],grantor=b['roles']['jous_security_reader'],grantee=b['roles'][role],
        privilege_type='EXECUTE',is_grantable=False) for h in c['helpers']
        for role in ('jous_runtime','jous_security_reader')]
    require(_multiset(acl,expected_acl),'HELPER_ACL')
    schema_acl=query(connection,CREATED_SCHEMA_ACL_SQL)
    expected_schema_acl=[dict(grantee=b['roles'][role],privilege_type='USAGE',is_grantable=False)
        for role in ('jous_runtime','jous_security_reader')]
    require(_multiset(schema_acl,expected_schema_acl),'SCHEMA_ACL')
    return _issue(VerifiedCreatedBindings,dict(contract=POLICY_SHA,
        existing_sha256=hashlib.sha256(existing.payload).hexdigest(),
        rows=sorted(rows,key=lambda r:r['proname']),
        acl=sorted(acl,key=canonical),schema_acl=sorted(schema_acl,key=canonical)))

def instantiate_policy_expectations(contract, existing, created):
    c=_read(contract,ApprovedFinalContract);b=_read(existing,VerifiedExistingBindings);h=_read(created,VerifiedCreatedBindings)
    require(b['contract']==h['contract']==POLICY_SHA and
        h['existing_sha256']==hashlib.sha256(existing.payload).hexdigest(),'POLICY_BINDING_MISMATCH')
    bindings={'relation:'+r['name']:r['oid'] for r in b['relations']}
    bindings.update({'helper:'+r['proname']:r['oid'] for r in h['rows']})
    clauses={}
    for t in c['templates']:
        raw=t['golden_raw'].encode()
        for slot in sorted(t['slots'],key=lambda s:s['offset'],reverse=True):
            value=bindings[slot['binding']];require(oid(value),'POLICY_BINDING_MISMATCH')
            pos=slot['offset'];raw=raw[:pos]+str(value).encode()+raw[pos+slot['length']:]
        clauses[t['policy']+'.'+t['clause']]=raw.decode('utf-8')
    records=[]
    for p in c['policies']:
        table=p['relation_binding'].split(':',1)[1]
        records.append(dict(relation_oid=bindings[p['relation_binding']],namespace='public',relation_name=table,
            owner_oid=b['roles']['postgres'],policy_name=p['policy_name'],command=p['command'],
            permissive=p['permissive'],role_oids=[b['roles'][p['role_binding'].split(':',1)[1]]],role_contract=True,
            using_tree=clauses.get(p['qual_template']),check_tree=clauses.get(p['with_check_template'])))
    return _issue(ExpectedPolicySet,records)

def collect_actual_policy_rows(connection,query,sql):
    return _issue(ObservedPolicySet,query(connection,sql))

def verify_policy_rows(expected,actual,continuity=None):
    wanted=_read(expected,ExpectedPolicySet);rows=_read(actual,ObservedPolicySet)
    key=lambda r:(r['relation_oid'],r['policy_name'])
    require(len(rows)==13 and len({key(r) for r in rows})==13 and
        {key(r) for r in rows}=={key(r) for r in wanted},'POLICY_INVENTORY_MISMATCH')
    ids=[r.get('policy_oid') for r in rows]
    require(all(oid(v) for v in ids) and len(set(ids))==13,'POLICY_INVENTORY_MISMATCH')
    by_key={key(r):r for r in wanted}
    for r in rows:
        w=by_key[key(r)];require(set(r)==set(w)|{'policy_oid'},'POLICY_INVENTORY_MISMATCH')
        exact({k:v for k,v in r.items() if k!='policy_oid'},w,'POLICY_TEMPLATE_MISMATCH')
    record=sorted(rows,key=key)
    if continuity is not None:
        exact(record,_read(continuity,VerifiedPolicyContinuity),'POLICY_CONTINUITY_MISMATCH')
    return _issue(VerifiedPolicyContinuity,record)
