"""Offline review tool, not imported by production: regenerate finite BKI contracts.
Field domains come from BKI catalog declarations, never token spelling alone.
"""
import hashlib
import json
from pathlib import Path
import re
import shlex

EVIDENCE = Path(__file__).parent/'fixtures/step7_pg17_11_catalog'
CATALOGS = {'types':'pg_type','functions':'pg_proc','operators':'pg_operator','collations':'pg_collation'}

def authority():
    receipt=json.loads((EVIDENCE/'AUTHORITY.json').read_bytes())
    for e in receipt['files']:
        raw=(EVIDENCE/e['path']).read_bytes()
        if len(raw)!=e['size'] or hashlib.sha256(raw).hexdigest()!=e['sha256']:
            raise ValueError('OFFLINE_AUTHORITY_HASH')
    config=(EVIDENCE/'include/server/pg_config.h').read_text()
    type_header=(EVIDENCE/'include/server/catalog/pg_type.h').read_text()
    auth=(EVIDENCE/'include/server/catalog/pg_authid_d.h').read_text()
    manual=(EVIDENCE/'include/server/pg_config_manual.h').read_text()
    if not (re.search(r'#define SIZEOF_VOID_P 8\b',config) and
            re.search(r'#define ALIGNOF_DOUBLE 8\b',config) and
            re.search(r"#define\s+TYPALIGN_DOUBLE\s+'d'",type_header) and re.search(r'#define BOOTSTRAP_SUPERUSERID 10\b',auth) and
            '#if SIZEOF_VOID_P >= 8' in manual and '#define USE_FLOAT8_BYVAL 1' in manual):
        raise ValueError('OFFLINE_PLATFORM_OR_OWNER')
    return receipt

def platform_macros():
    authority()
    config=(EVIDENCE/'include/server/pg_config.h').read_text()
    size=int(re.search(r'#define SIZEOF_VOID_P (\d+)',config)[1])
    alignment=re.search(r"#define\s+TYPALIGN_DOUBLE\s+'(.)'",(EVIDENCE/'include/server/catalog/pg_type.h').read_text())[1]
    # This resolver is only for the frozen Windows AMD64 platform (eight-byte pointer/alignment).
    return {'SIZEOF_POINTER':size,'ALIGNOF_POINTER':alignment}

def catalog(name, ids):
    macros=platform_macros()
    raw=(EVIDENCE/'share/postgres.bki').read_text()
    section=raw[raw.index('create '+name+' '):];section=section[:section.index('close '+name)]
    fields=re.findall(r'^ (\w+) = (\w+)',section[:section.index('\n )')],re.M)
    result={}
    for line in section.splitlines():
        if line.startswith('insert '):
            tokens=shlex.split(line[line.index('(')+1:line.rindex(')')])
            if len(tokens)!=len(fields):raise ValueError('BKI_ARITY')
            if int(tokens[0]) not in ids:continue
            record={}
            for (field,domain),token in zip(fields,tokens):
                if token=='_null_': value=None
                elif domain=='bool':
                    if token=='FLOAT8PASSBYVAL':value=True # approved 64-bit Datum platform
                    elif token in ('t','f'):value=token=='t'
                    else:raise ValueError('BKI_BOOLEAN')
                elif domain in ('int2','int4','oid','regproc'):
                    if field=='typlen' and token=='SIZEOF_POINTER':value=macros[token]
                    elif token=='-' and domain=='regproc':value=0
                    elif re.fullmatch(r'-?\d+',token):value=int(token)
                    else:raise ValueError('BKI_INTEGER_OR_MACRO:'+field)
                elif domain=='char':
                    if field=='typalign' and token=='ALIGNOF_POINTER':value=macros[token]
                    elif len(token)==1:value=token
                    else:raise ValueError('BKI_CHAR_OR_MACRO:'+field)
                else:value=token # names/text/vectors decoded only by explicitly selected projection
                record[field]=value
            result[record['oid']]=record
    return result

def regenerate(data):
    receipt=authority()
    out=json.loads(json.dumps(data))
    for kind,table in CATALOGS.items():
        raw=catalog(table,{r['oid'] for r in out['builtins'][kind]})
        ownerfield={'types':'typowner','functions':'proowner','operators':'oprowner','collations':'collowner'}[kind]
        for row in out['builtins'][kind]:
            source=raw[row['oid']]
            for key in list(row):
                if key in source:row[key]=source[key]
            if source[ownerfield]!=10:raise ValueError('BKI_BOOTSTRAP_OWNER')
            row[ownerfield]=10;row['owner']='supabase_admin'
            if kind=='functions':
                row['input_oids']=[int(x) for x in source['proargtypes'].split()]
                row['no_defaults']=source['proargdefaults'] is None
                row['no_sql_body']=source['prosqlbody'] is None
    # Additional provenance only; original hashes and every non-built-in contract retained.
    for e in receipt['files']:
        if not any(p['source']==e['source'] for p in out['provenance']):
            out['provenance'].append({k:e[k] for k in ('source','size','sha256')})
    return out

if __name__=='__main__':
    import sys
    path=Path(sys.argv[1]);data=regenerate(json.loads(path.read_bytes()))
    path.write_bytes((json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False)+'\n').encode())
