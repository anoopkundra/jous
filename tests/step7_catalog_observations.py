"""Independent test authority reader. Does not import the contract or its generator.
The retained JSON mock is reviewed against raw BKI declarations by this reader.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex

ROOT=Path(__file__).parent/'fixtures/step7_pg17_11_catalog'
IDS={'types':(16,21,23,25,26,701,1009,1015,1043,1184,2275,2281,2950),
 'functions':(47,65,67,101,102,105,106,144,157,1254,1256,1317,1364,1818,1821,1824,1827,2952,2956,2959,3294),
 'operators':(96,98,518,531,641,642,2972,2973),'collations':(100,)}
FIELDS={'types':'oid typname typnamespace typtype typcategory typlen typbyval typalign typstorage typelem typarray typcollation typinput typoutput typbasetype typrelid typowner',
 'functions':'oid proname pronamespace prolang prokind prosecdef provolatile proparallel proisstrict proleakproof proretset prorettype provariadic pronargdefaults prosupport proconfig probin prosrc proowner',
 'operators':'oid oprname oprnamespace oprkind oprcanmerge oprcanhash oprleft oprright oprresult oprcom oprnegate oprcode oprrest oprjoin oprowner',
 'collations':'oid collname collprovider collisdeterministic collencoding collcollate collctype colllocale collicurules collversion collowner'}

def from_authority():
    raw_receipt=(ROOT/'AUTHORITY.json').read_bytes()
    assert hashlib.sha256(raw_receipt).hexdigest()=='5a7861ddc11a7b81d2238a70c16d8628c07bb8f2a968d7d93cfcdd10ac97641a'
    receipt=json.loads(raw_receipt)
    for entry in receipt['files']:
        raw=(ROOT/entry['path']).read_bytes()
        assert len(raw)==entry['size'] and hashlib.sha256(raw).hexdigest()==entry['sha256']
    bki=(ROOT/'share/postgres.bki').read_text()
    config=(ROOT/'include/server/pg_config.h').read_text()
    assert '#define SIZEOF_VOID_P 8' in config and '#define ALIGNOF_DOUBLE 8' in config
    assert '#define BOOTSTRAP_SUPERUSERID 10' in (ROOT/'include/server/catalog/pg_authid_d.h').read_text()
    material={}
    for group,ids in IDS.items():
        name={'types':'pg_type','functions':'pg_proc','operators':'pg_operator','collations':'pg_collation'}[group]
        section=bki.split('create '+name+' ',1)[1].split('close '+name,1)[0]
        declarations=re.findall(r'^ (\w+) = (\w+)',section.split('\n )',1)[0],re.M)
        rows=[]
        for line in section.splitlines():
            if not line.startswith('insert '):continue
            words=shlex.split(line.partition('(')[2].rpartition(')')[0])
            if int(words[0]) not in ids:continue
            tokens=dict(zip((k for k,t in declarations),words))
            domains=dict(declarations)
            row={}
            for field in FIELDS[group].split():
                word=tokens[field];domain=domains[field]
                if word=='_null_':value=None
                elif domain=='bool':
                    assert word in ('t','f','FLOAT8PASSBYVAL')
                    value=word in ('t','FLOAT8PASSBYVAL')
                elif domain=='char':
                    value={'ALIGNOF_POINTER':'d'}.get(word,word)
                    assert len(value)==1
                elif domain in ('oid','int2','int4','regproc'):
                    value=int({'SIZEOF_POINTER':'8','-':'0'}.get(word,word))
                else:value=word
                row[field]=value
            row['schema']='pg_catalog';row['owner']='supabase_admin'
            if group=='functions':
                row.update(language='internal',input_oids=list(map(int,tokens['proargtypes'].split())),
                    no_defaults=tokens['proargdefaults']=='_null_',no_sql_body=tokens['prosqlbody']=='_null_')
            if group=='collations':row['namespace_oid']=int(tokens['collnamespace'])
            rows.append(row)
        assert {r['oid'] for r in rows}==set(ids)
        material[group]=sorted(rows,key=lambda r:r['oid'])
    return material

def observations():
    # Retained mock is separate data; no expected artifact is consulted.
    raw=(ROOT/'catalog_observations.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='968def8d7b8112d5581d2fa0e1dcc08a22a23444fb894fff4c74c983600d7d65'
    return json.loads(raw)
