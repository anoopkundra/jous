"""Fail-closed successor profile; catalog expectations come only from reviewed source.

PostgreSQL rendering equivalence is deliberately strict. The separately gated
disposable PostgreSQL gate must establish the exact catalog rendering before
operational adoption; mock tests are not database security certification.
"""
import re
import sys
from contextlib import contextmanager
from time import perf_counter
from sqlalchemy import text, CheckConstraint, ForeignKeyConstraint, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.dialects.postgresql import dialect
from .database import (DatabaseUnavailable, validate_product_foundation,
                       validate_route_economics_foundation,
                       validate_usage_events_foundation)
from .runtime_resolution import catalog_resolution
from .task_models import tasks, executions, POLICIES, TASK_COLUMNS, EXECUTION_COLUMNS
from .product_policy_canonicalization import canonical_policy_expression

TABLES = (tasks, executions)
COLUMNS_SQL = """SELECT c.relname::text, a.attname::text, pg_catalog.format_type(a.atttypid,a.atttypmod),
 a.attnotnull, pg_catalog.pg_get_expr(d.adbin,d.adrelid), a.attnum
 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
 LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
 WHERE n.nspname='public' AND c.relname IN ('tasks','executions') AND a.attnum>0 AND NOT a.attisdropped
 ORDER BY c.relname,a.attnum"""
CONSTRAINTS_SQL = """SELECT c.relname::text,k.conname::text,k.contype::text,k.condeferrable,k.condeferred,k.convalidated,
 ARRAY(SELECT a.attname::text FROM unnest(k.conkey) WITH ORDINALITY v(num,ord)
       JOIN pg_catalog.pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=v.num ORDER BY v.ord),
 rn.nspname::text,rc.relname::text,
 ARRAY(SELECT a.attname::text FROM unnest(k.confkey) WITH ORDINALITY v(num,ord)
       JOIN pg_catalog.pg_attribute a ON a.attrelid=k.confrelid AND a.attnum=v.num ORDER BY v.ord),
 k.confupdtype::text,k.confdeltype::text,pg_catalog.pg_get_expr(k.conbin,k.conrelid)
 FROM pg_catalog.pg_constraint k JOIN pg_catalog.pg_class c ON c.oid=k.conrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 LEFT JOIN pg_catalog.pg_class rc ON rc.oid=k.confrelid
 LEFT JOIN pg_catalog.pg_namespace rn ON rn.oid=rc.relnamespace
 WHERE n.nspname='public' AND (c.relname IN ('tasks','executions') OR
 (c.relname='projects' AND k.conname='uq_projects_organization_id_id'))"""
POLICIES_SQL = """SELECT c.relname::text,p.polname::text,p.polcmd::text,p.polpermissive,
 ARRAY(SELECT r.rolname::text FROM pg_catalog.pg_roles r WHERE r.oid=ANY(p.polroles) ORDER BY r.rolname),
 pg_catalog.pg_get_expr(p.polqual,p.polrelid),pg_catalog.pg_get_expr(p.polwithcheck,p.polrelid)
 FROM pg_catalog.pg_policy p JOIN pg_catalog.pg_class c ON c.oid=p.polrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
 WHERE n.nspname='public' AND c.relname IN ('tasks','executions')"""
INDEXES_SQL = """SELECT c.relname::text,i.relname::text,x.indisunique,x.indisvalid,x.indisready,x.indimmediate,
 x.indpred IS NULL,x.indexprs IS NULL,am.amname::text,
 ARRAY(SELECT a.attname::text FROM unnest(x.indkey) WITH ORDINALITY v(num,ord)
 JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid AND a.attnum=v.num ORDER BY v.ord),
 x.indnkeyatts,x.indnatts
 FROM pg_catalog.pg_index x JOIN pg_catalog.pg_class c ON c.oid=x.indrelid
 JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace JOIN pg_catalog.pg_class i ON i.oid=x.indexrelid
 JOIN pg_catalog.pg_am am ON am.oid=i.relam
 WHERE n.nspname='public' AND (c.relname IN ('tasks','executions') OR
 (c.relname='projects' AND i.relname='uq_projects_organization_id_id'))"""


def expression(value):
    # Whitespace only: never erase operators/casts/clauses to force a match.
    return re.sub(r'\s+', ' ', value).strip() if value is not None else None


ERROR_CODE_VALUES = (
    'not_dispatched', 'supplier_rejected', 'rate_limited', 'malformed_response',
    'response_too_large', 'metadata_inconsistent', 'transport_ambiguous',
    'provider_timeout',
)
ERROR_CODE_MIGRATION_EXPRESSION = (
    "error_code IS NULL OR error_code IN (" +
    ','.join("'" + value + "'" for value in ERROR_CODE_VALUES) + ')'
)
ERROR_CODE_CATALOG_EXPRESSION = (
    '((error_code IS NULL) OR (error_code = ANY (ARRAY[' +
    ', '.join("'" + value + "'::text" for value in ERROR_CODE_VALUES) + '])))'
)


def canonical_error_code_expression(value):
    """Accept only the migration expression or its exact PostgreSQL rendering."""
    rendered = expression(value)
    if rendered in (ERROR_CODE_MIGRATION_EXPRESSION, ERROR_CODE_CATALOG_EXPRESSION):
        return ERROR_CODE_MIGRATION_EXPRESSION
    return None


def _check_tokens(source):
    """Tokenize CHECK SQL without changing quoted constants or identifiers."""
    tokens=[];i=0
    operators=('->>','#>>','!~*','::','<=','>=','<>','!=','||','->','#>','@>','<@','?&','?|','!~','~*')
    while i<len(source):
        ch=source[i]
        if ch.isspace():
            i+=1;continue
        if source.startswith('--',i) or source.startswith('/*',i) or ch==';':
            return None
        if ch=="'":
            start=i;i+=1
            while i<len(source):
                if source[i]=='\\':
                    i+=2;continue
                if source[i]=="'":
                    if i+1<len(source) and source[i+1]=="'":i+=2;continue
                    i+=1;break
                i+=1
            else:return None
            tokens.append(('literal',source[start:i]));continue
        if ch=='"':
            start=i;i+=1
            while i<len(source):
                if source[i]=='"':
                    if i+1<len(source) and source[i+1]=='"':i+=2;continue
                    i+=1;break
                i+=1
            else:return None
            tokens.append(('quoted_identifier',source[start:i]));continue
        if ch.isalpha() or ch=='_' or ord(ch)>=128:
            start=i;i+=1
            while i<len(source) and (source[i].isalnum() or source[i] in '_$' or ord(source[i])>=128):i+=1
            tokens.append(('word',source[start:i]));continue
        if ch.isdigit() or (ch=='.' and i+1<len(source) and source[i+1].isdigit()):
            match=re.match(r'(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',source[i:])
            tokens.append(('number',match.group(0)));i+=len(match.group(0));continue
        operator=next((op for op in operators if source.startswith(op,i)),None)
        if operator:
            tokens.append(('operator',operator));i+=len(operator);continue
        if ch in '()[]{},.=:<>+-*/%~!^|&?':
            tokens.append(('punctuation' if ch in '()[]{},.' else 'operator',ch));i+=1;continue
        # Unknown syntax is rejected instead of being normalized permissively.
        return None
    return tokens


def _check_delimiters(tokens):
    pairs={')':'(',']':'[','}':'{'};stack=[]
    for kind,value in tokens:
        if kind!='punctuation':continue
        if value in '([{':stack.append(value)
        elif value in ')]}':
            if not stack or stack.pop()!=pairs[value]:return False
    return not stack


def _outer_check_group(tokens):
    if not tokens or tokens[0] != ('punctuation','('):return False
    depth=0
    for i,token in enumerate(tokens):
        if token==('punctuation','('):depth+=1
        elif token==('punctuation',')'):
            depth-=1
            if depth==0:return i==len(tokens)-1
    return False


def _top_level_check_splits(tokens,keyword, *, route_economics=False):
    stack=[];pairs={')':'(',']':'[','}':'{'};splits=[];top_level=[]
    for i,(kind,value) in enumerate(tokens):
        top_level.append(not stack)
        if kind=='punctuation':
            if value in '([{':stack.append(value)
            elif value in ')]}':
                if not stack or stack.pop()!=pairs[value]:return None
    for i,(kind,value) in enumerate(tokens):
        if not top_level[i] or kind!='word' or value.upper()!=keyword:
            continue
        if (not route_economics and keyword=='AND' and i>=3 and i+1<len(tokens)
                and top_level[i-3] and top_level[i-2] and top_level[i-1]
                and top_level[i+1] and tokens[i-3][0] in ('word','quoted_identifier')
                and tokens[i-2][0]=='word' and tokens[i-2][1].upper()=='BETWEEN'
                and tokens[i-1][0]=='number' and tokens[i+1][0]=='number'):
            continue
        if (route_economics and keyword=='AND' and i>0 and i+1<len(tokens)
                and tokens[i-1][0]=='number' and tokens[i+1][0]=='number'):
            between_positions=[j for j in range(i-1) if top_level[j] and
                               tokens[j][0]=='word' and tokens[j][1].upper()=='BETWEEN']
            if (between_positions and between_positions[-1]+1<=i-1
                    and all(tokens[j][0]!='word' or tokens[j][1].upper()!='BETWEEN'
                            for j in range(between_positions[-1]+1,i))):
                # This AND is the separator in BETWEEN <numeric> AND <numeric>,
                # including a structurally preserved function-call LHS.
                continue
        splits.append(i)
    return splits


_ROUTE_ECONOMICS_CHECKS = {
    ('route_pricing_versions', name) for name in (
        'ck_route_pricing_version_positive', 'ck_route_pricing_currency',
        'ck_route_pricing_billing', 'ck_route_pricing_rates',
        'ck_route_pricing_provider_fee', 'ck_route_pricing_gateway_fee',
        'ck_route_pricing_approval', 'ck_route_pricing_source',
        'ck_route_pricing_evidence')
} | {
    ('route_pricing_revocations', 'ck_route_pricing_revocation_fields'),
} | {
    ('route_decisions', name) for name in (
        'ck_route_decisions_snapshot', 'ck_route_decisions_snapshot_binding',
        'ck_route_decisions_hash', 'ck_route_decisions_snapshot_digest',
        'ck_route_decisions_currency', 'ck_route_decisions_route_version',
        'ck_route_decisions_token_bounds', 'ck_route_decisions_estimate',
        'ck_route_decisions_identity')
}

_ROUTE_ECONOMICS_TEXT_COLUMNS = {
    'pricing_version_id', 'route_id', 'service_tier', 'currency', 'billing_basis',
    'pricing_status', 'source_type', 'source_evidence_id', 'reason_code', 'evidence_id',
    'decision_version', 'selector_version', 'logical_model_id', 'selected_route_id',
}


def _route_economics_catalog_tokens(tokens):
    """Normalize only PostgreSQL 17's observed coercions in V1.3 CHECKs.

    This is opt-in from the CHECK AST entrypoint after table/constraint allowlisting.
    It preserves operators, field names, literals, array order and non-text casts.
    """
    tokens=list(tokens)
    builtins={'isfinite','jsonb_typeof','jsonb_array_length','sha256','convert_to'}
    result=[];i=0
    while i<len(tokens):
        if (i+4<len(tokens) and tuple(tokens[i:i+5])==(
                ('operator','::'),('word','timestamp'),('word','with'),('word','time'),('word','zone'))):
            result.extend((('operator','::'),('word','timestamptz')));i+=5;continue
        # PostgreSQL deparses a schema-qualified built-in without qualification.
        if (i+2<len(tokens) and tuple(tokens[i:i+2])==(('word','pg_catalog'),('punctuation','.'))
                and tokens[i+2][0]=='word' and tokens[i+2][1] in builtins):
            result.append(tokens[i+2]);i+=3;continue
        # Varchar/text columns are relabeled to text by PostgreSQL in comparison
        # and btrim contexts. The exact column allowlist comes from 0005's schema.
        if (i+2<len(tokens) and tokens[i][0] in ('word','quoted_identifier')
                and tokens[i][1] in _ROUTE_ECONOMICS_TEXT_COLUMNS
                and tuple(tokens[i+1:i+3])==(('operator','::'),('word','text'))):
            result.append(tokens[i]);i+=3;continue
        # A parenthesized numeric zero cast to numeric is PostgreSQL's rendering
        # of the source integer literal in the approved numeric >= 0 checks.
        if (i+4<len(tokens) and tokens[i]==('punctuation','(')
                and tokens[i+1]==('number','0') and tokens[i+2]==('punctuation',')')
                and tokens[i+3]==('operator','::') and tokens[i+4]==('word','numeric')):
            result.append(('number','0'));i+=5;continue
        # convert_to's encoding argument has type name; PostgreSQL deparses the
        # source's unknown string literal with an explicit ::name coercion.
        if (i+3<len(tokens) and tokens[i]==('literal',"'UTF8'")
                and tuple(tokens[i+1:i+3])==(('operator','::'),('word','name'))):
            result.append(tokens[i]);i+=3;continue
        # Text casts on literal operands are accepted only in text comparison or
        # JSON key positions. Cast targets elsewhere remain part of the AST.
        if (i+2<len(tokens) and tokens[i][0]=='literal'
                and tuple(tokens[i+1:i+3])==(('operator','::'),('word','text'))
                and (result and result[-1] in (('operator','='),('operator','<>'),
                     ('operator','->'),('operator','->>')))):
            result.append(tokens[i]);i+=3;continue
        result.append(tokens[i]);i+=1
    tokens=tuple(result)
    # PostgreSQL adds one redundant group around a sole JSON function argument,
    # or around a JSON operator expression before its explicitly preserved cast.
    # Strip only those syntactically matched wrappers; casts/operators remain.
    changed=True
    while changed:
        changed=False;stack=[];pairs={')':'(',']':'[','}':'{'}
        for i,token in enumerate(tokens):
            if token==('punctuation','('):stack.append(i)
            elif token==('punctuation',')') and stack:
                start=stack.pop()
                if start+1>=i:continue
                function_argument=(start>=2 and tokens[start-1]==('punctuation','(')
                    and tokens[start-2][0]=='word' and tokens[start-2][1] in
                    {'jsonb_typeof','jsonb_array_length','length','btrim'}
                    and i+1<len(tokens) and tokens[i+1]==('punctuation',')'))
                cast_operand=(i+2<len(tokens) and tokens[i+1]==('operator','::')
                    and tokens[i+2][0]=='word'
                    and any(t in (('operator','->'),('operator','->>')) for t in tokens[start+1:i]))
                json_chain_operand=(i+1<len(tokens)
                    and tokens[i+1] in (('operator','->'),('operator','->>'))
                    and any(t in (('operator','->'),('operator','->>')) for t in tokens[start+1:i]))
                comparison_operand=(i+1<len(tokens)
                    and tokens[i+1] in (('operator','='),('operator','<>'),('operator','!='),
                                        ('operator','<'),('operator','<='),('operator','>'),('operator','>='))
                    and any(t in (('operator','->'),('operator','->>')) for t in tokens[start+1:i]))
                if function_argument or cast_operand or json_chain_operand or comparison_operand:
                    tokens=tokens[:start]+tokens[start+1:i]+tokens[i+1:]
                    changed=True;break
    return tokens


def _canonical_check_node(tokens, *, route_economics=False, check_name=None):
    if not tokens:return None
    while _outer_check_group(tokens):
        tokens=tokens[1:-1]
        if not tokens:return None
    # PostgreSQL CHECK accepts both TRUE and NULL. The successor constraint
    # uses IS TRUE to reject UNKNOWN; recognize this wrapper only for that one
    # explicitly scoped route-economics constraint.
    if (route_economics and check_name=='ck_route_decisions_snapshot_binding'
            and len(tokens)>=4
            and tuple(tokens[-2:])==(('word','IS'),('word','TRUE'))):
        predicate=tokens[:-2]
        if _outer_check_group(predicate):
            predicate=predicate[1:-1]
        child=_canonical_check_node(predicate,route_economics=True,check_name=check_name)
        return None if child is None else ('IS_TRUE',(child,))
    # Normalize only identifier BETWEEN numeric AND numeric. The splitter
    # above protects its internal AND so the form arrives here intact.
    if (not route_economics and len(tokens)==5 and tokens[0][0] in ('word','quoted_identifier')
            and tokens[1][0]=='word' and tokens[1][1].upper()=='BETWEEN'
            and tokens[2][0]=='number' and tokens[3][0]=='word'
            and tokens[3][1].upper()=='AND' and tokens[4][0]=='number'):
        identifier=tokens[0]
        return ('AND',(('ATOM',(identifier,('operator','>='),tokens[2])),
                       ('ATOM',(identifier,('operator','<='),tokens[4]))))
    # Split at SQL boolean precedence without reordering, flattening, or
    # replacing operators. Parenthesized children retain their own tree.
    for keyword in ('OR','AND'):
        splits=_top_level_check_splits(tokens,keyword,route_economics=route_economics)
        if splits is None:return None
        if splits:
            boundaries=[-1,*splits,len(tokens)]
            children=[]
            for left,right in zip(boundaries,boundaries[1:]):
                child=_canonical_check_node(tokens[left+1:right],route_economics=route_economics,
                                            check_name=check_name)
                if child is None:return None
                children.append(child)
            return (keyword,tuple(children))
    # PostgreSQL expands inclusive BETWEEN into >= / <=. Preserve the complete
    # parsed left expression and both numeric endpoints in the resulting tree.
    depth=0;between_at=[];and_at=[]
    for i,(kind,value) in enumerate(tokens):
        if kind=='punctuation':
            if value in '([{':depth+=1
            elif value in ')]}':depth-=1
        elif depth==0 and kind=='word':
            if value.upper()=='BETWEEN':between_at.append(i)
            elif value.upper()=='AND':and_at.append(i)
    if route_economics and between_at:
        if len(between_at)!=1:return None
        start=between_at[0]
        delimiters=[i for i in and_at if i>start]
        if (not start or not delimiters or len(tokens[start+1:delimiters[0]])!=1
                or tokens[start+1][0]!='number' or delimiters[0]+2!=len(tokens)
                or tokens[delimiters[0]+1][0]!='number'):
            return None
        left=tokens[:start]
        lower=tokens[start+1]
        upper=tokens[delimiters[0]+1]
        low=_canonical_check_atom((*left,('operator','>='),lower),
                                  route_economics=route_economics)
        high=_canonical_check_atom((*left,('operator','<='),upper),
                                   route_economics=route_economics)
        if low is None or high is None:return None
        return ('AND',(low,high))
    # Reject common incomplete predicates/operators. All other atom tokens
    # remain exact, including casts, identifiers, literals, and operators.
    top=[];stack=[];pairs={')':'(',']':'[','}':'{'}
    for token in tokens:
        kind,value=token
        if kind=='punctuation':
            if value in '([{':stack.append(value)
            elif value in ')]}':
                if not stack or stack.pop()!=pairs[value]:return None
            if not stack:top.append(token)
        elif not stack:top.append(token)
    if stack or not top:return None
    if any(kind=='word' and value.upper()=='BETWEEN' for kind,value in tokens):
        # Unsupported or malformed BETWEEN syntax is never accepted as an
        # opaque atom.
        return None
    binary={'=','<>','!=','<','<=','>','>=','::','||','->','->>','#>','#>>','@>','<@','?','?&','?|','!~','!~*','~','~*','*','/','%','^'}
    if (top[-1][1] in binary or top[-1][1] in ('AND','OR','IS','IN','LIKE','ILIKE','BETWEEN','NOT')
            or top[0][1] in binary-{'+' , '-'} or top[0][1] in ('AND','OR','IS','IN','LIKE','ILIKE','BETWEEN')):
        return None
    return _canonical_check_atom(tuple(tokens),route_economics=route_economics)


def _string_literal_list(values, *, allow_text_cast, allow_varchar_cast=False):
    """Parse only a nonempty ordered list of SQL string-literal tokens."""
    if not values:
        return None
    result=[];i=0
    while i<len(values):
        if values[i][0]!='literal':return None
        result.append(values[i]);i+=1
        if i<len(values) and values[i]==('operator','::'):
            if allow_text_cast and i+1<len(values) and values[i+1]==('word','text'):
                i+=2
            elif (allow_varchar_cast and i+2<len(values)
                  and tuple(values[i+1:i+3])==(('word','character'),('word','varying'))):
                i+=3
            else:return None
        if i==len(values):break
        if values[i]!=('punctuation',','):return None
        i+=1
        if i==len(values):return None
    return tuple(result)


def _canonical_in_any_atom(tokens, *, route_economics=False):
    """Recognize only identifier IN(list) and its literal ARRAY ANY form."""
    has_in_any=any(kind=='word' and value.upper() in ('IN','ANY') for kind,value in tokens)
    if not has_in_any:
        return False,None
    if (len(tokens)>=5 and tokens[0][0] in ('word','quoted_identifier')
            and tokens[1][0]=='word' and tokens[1][1].upper()=='IN'
            and tokens[2]==('punctuation','(') and tokens[-1]==('punctuation',')')):
        members=_string_literal_list(tokens[3:-1],allow_text_cast=True)
        if members is not None:
            return True,('IN_LIST',(tokens[0],members))
        return True,None
    if (len(tokens)>=9 and tokens[0][0] in ('word','quoted_identifier')
            and tokens[1]==('operator','=') and tokens[2][0]=='word'
            and tokens[2][1].upper()=='ANY' and tokens[3]==('punctuation','(')
            and tokens[4][0]=='word' and tokens[4][1].upper()=='ARRAY'
            and tokens[5]==('punctuation','[') and tokens[-2]==('punctuation',']')
            and tokens[-1]==('punctuation',')')):
        members=_string_literal_list(tokens[6:-2],allow_text_cast=True)
        if members is not None:
            return True,('IN_LIST',(tokens[0],members))
        return True,None
    # Exact PostgreSQL 17 rendering of varchar IN(string literals):
    # lhs = ANY ((ARRAY['a'::character varying,...])::text[])
    # Only the ordered, nonempty literal array and these exact element/result
    # types are accepted; arbitrary ANY expressions remain unsupported.
    if (route_economics and len(tokens)>=15
            and tokens[0][0] in ('word','quoted_identifier')
            and tokens[1]==('operator','=') and tokens[2]==('word','ANY')
            and tuple(tokens[3:6])==(('punctuation','('),('punctuation','('),('word','ARRAY'))
            and tokens[6]==('punctuation','[')
            and tuple(tokens[-7:])==(('punctuation',']'),('punctuation',')'),('operator','::'),
                              ('word','text'),('punctuation','['),('punctuation',']'),
                              ('punctuation',')'))):
        members=_string_literal_list(tokens[7:-7],allow_text_cast=False,allow_varchar_cast=True)
        if members is not None:
            return True,('IN_LIST',(tokens[0],members))
        return True,None
    # Do not pass an unrecognized IN/ANY construct through as an opaque atom.
    return True,None


def _canonical_literal_text_comparison(tokens):
    """Drop a literal's redundant ::text cast in a bounded comparison."""
    # identifier = 'literal'::text
    if (len(tokens)==5 and tokens[0][0] in ('word','quoted_identifier')
            and tokens[1]==('operator','=') and tokens[2][0]=='literal'
            and tokens[3]==('operator','::') and tokens[4]==('word','text')):
        return ('ATOM',(tokens[0],tokens[1],tokens[2]))
    # identifier IS DISTINCT FROM 'literal'::text
    if (len(tokens)==7 and tokens[0][0] in ('word','quoted_identifier')
            and tuple(tokens[1:4])==(('word','IS'),('word','DISTINCT'),('word','FROM'))
            and tokens[4][0]=='literal' and tokens[5]==('operator','::')
            and tokens[6]==('word','text')):
        return ('ATOM',(tokens[0],*tokens[1:5]))
    # A simple function call may be the LHS, but only when its entire
    # argument list is a comma-separated sequence of bare identifiers.
    # This deliberately excludes nested calls, operators, and casts.
    function_end=None;function_close=None
    if (len(tokens)>=3 and tokens[0][0] in ('word','quoted_identifier')
            and tokens[1]==('punctuation','(')):
        depth=0
        for j in range(1,len(tokens)):
            if tokens[j]==('punctuation','('):depth+=1
            elif tokens[j]==('punctuation',')'):
                depth-=1
                if depth==0:
                    function_close=j;break
        i=2
        valid=True
        if (tokens[0]==('word','jsonb_typeof') and function_close==5
                and tokens[2][0] in ('word','quoted_identifier')
                and tokens[3]==('operator','->') and tokens[4][0]=='literal'):
            function_end=function_close+1
        elif function_close==i and i<len(tokens):
            function_end=i+1
        else:
            while valid:
                if i>=len(tokens) or tokens[i][0] not in ('word','quoted_identifier'):
                    valid=False;break
                i+=1
                if i<len(tokens) and tokens[i]==('punctuation',','):
                    i+=1
                    continue
                if i<len(tokens) and tokens[i]==('punctuation',')'):
                    function_end=i+1
                    break
                valid=False
        if not valid or (function_end is not None and function_end!=function_close+1):
            function_end=None
    function_comparison=(function_close is not None and function_close+2<len(tokens)
                         and tokens[function_close+1]==('operator','=')
                         and tokens[function_close+2][0]=='literal')
    if function_comparison:
        rhs=tokens[function_close+2:]
        rhs_is_literal=(len(rhs)==1 or
                        (len(rhs)==3 and rhs[1]==('operator','::')
                         and rhs[2]==('word','text')))
        if not rhs_is_literal:return None
        if function_end is None:
            args=tokens[2:function_close]
            if (args and (args[0]==('punctuation',',')
                          or args[-1]==('punctuation',',')
                          or any(args[i]==('punctuation',',')
                                 and args[i+1]==('punctuation',',')
                                 for i in range(len(args)-1)))):
                return None
            # Valid but unsupported argument expressions remain exact, so
            # they cannot gain equivalence from this narrow rule.
            return ('ATOM',tokens)
        if len(rhs)==3:
            return ('ATOM',tokens[:function_end+2])
        return ('ATOM',tokens)
    return ('ATOM',tokens)


def _canonical_json_text_key_casts(tokens):
    """Remove ::text only from proven JSON text-key operands."""
    # `identifier ? 'key'::text` and `identifier -> 'key'::text`.
    result=[];i=0
    while i<len(tokens):
        if (i>=1 and tokens[i][0]=='literal'
                and tokens[i-1] in (('operator','?'),('operator','->'))
                and i+2<len(tokens) and tokens[i+1]==('operator','::')
                and tokens[i+2]==('word','text')):
            result.append(tokens[i]);i+=3
        else:
            result.append(tokens[i]);i+=1
    tokens=tuple(result)

    # PostgreSQL groups the extraction only in these two observed contexts:
    # as the sole jsonb_typeof argument, or as a JSONB equality's LHS.
    if (len(tokens)>=8 and tokens[0]==('word','jsonb_typeof')
            and tokens[1]==('punctuation','(')
            and tokens[2]==('punctuation','(')
            and tokens[3][0] in ('word','quoted_identifier')
            and tokens[4]==('operator','->') and tokens[5][0]=='literal'
            and tokens[6]==('punctuation',')')
            and tokens[7]==('punctuation',')')):
        tokens=tokens[:2]+tokens[3:6]+tokens[7:]
    elif (len(tokens)>=6 and tokens[0]==('punctuation','(')
            and tokens[1][0] in ('word','quoted_identifier')
            and tokens[2]==('operator','->') and tokens[3][0]=='literal'
            and tokens[4]==('punctuation',')')
            and tokens[5]==('operator','=')):
        tokens=tokens[1:4]+tokens[5:]

    # `identifier ?& ARRAY['key'::text,...]` only: validate an ordered list
    # of string literals, then remove only their explicit text casts.
    if (len(tokens)>=6 and tokens[0][0] in ('word','quoted_identifier')
            and tokens[1]==('operator','?&')
            and tokens[2]==('word','ARRAY')
            and tokens[3]==('punctuation','[')
            and tokens[-1]==('punctuation',']')):
        members=_string_literal_list(tokens[4:-1],allow_text_cast=True)
        if members is not None:
            normalized=[tokens[0],tokens[1],tokens[2],tokens[3]]
            for i,member in enumerate(members):
                if i:normalized.append(('punctuation',','))
                normalized.append(member)
            normalized.append(tokens[-1])
            tokens=tuple(normalized)

    return tokens


def _canonical_simple_identifier_cast_operand(tokens):
    """Remove only the redundant parens around an identifier before ::type.

    PostgreSQL may render ``(identifier)::type`` where the model renders
    ``identifier::type``. Keep the cast and its target tokens intact, and do
    not unwrap any compound, function, or nested expression.
    """
    result=[];i=0
    while i<len(tokens):
        if (i+4<len(tokens)
                and tokens[i]==('punctuation','(')
                and tokens[i+1][0] in ('word','quoted_identifier')
                and tokens[i+2]==('punctuation',')')
                and tokens[i+3]==('operator','::')
                and tokens[i+4][0] in ('word','quoted_identifier')):
            result.extend((tokens[i+1],tokens[i+3],tokens[i+4]))
            i+=5
        else:
            result.append(tokens[i]);i+=1
    return tuple(result)


def _canonical_40_second_interval_comparison(tokens):
    """Match only the two evidenced forms of the 40-second deadline bound."""
    identifier_kinds=('word','quoted_identifier')
    if (len(tokens)==6 and tokens[0][0] in identifier_kinds
            and tokens[1]==('operator','<=')
            and tokens[2][0] in identifier_kinds
            and tokens[3]==('operator','+')
            and tokens[4]==('word','interval')
            and tokens[5]==('literal',"'40 seconds'")):
        return True,('ATOM',tokens)
    if (len(tokens)==9 and tokens[0][0] in identifier_kinds
            and tokens[1]==('operator','<=')
            and tokens[2]==('punctuation','(')
            and tokens[3][0] in identifier_kinds
            and tokens[4]==('operator','+')
            and tokens[5]==('literal',"'00:00:40'")
            and tokens[6]==('operator','::')
            and tokens[7]==('word','interval')
            and tokens[8]==('punctuation',')')):
        return True,('ATOM',(tokens[0],tokens[1],tokens[3],tokens[4],
                              ('word','interval'),('literal',"'40 seconds'")))
    return False,None


def _canonical_identifier_addition_comparison(tokens):
    """Canonicalize only a three-identifier left-associative sum comparison."""
    identifier_kinds=('word','quoted_identifier')
    if (len(tokens)==7 and all(tokens[i][0] in identifier_kinds for i in (0,2,4))
            and tokens[1]==('operator','+') and tokens[3]==('operator','+')
            and tokens[5]==('operator','<=') and tokens[6][0]=='number'):
        return ('ATOM',(tokens[0],tokens[1],tokens[2],tokens[3],tokens[4],
                        tokens[5],tokens[6]))
    # Exact PostgreSQL grouping: ((identifier + identifier) + identifier)
    # <= numeric. No other arithmetic/grouping form is unwrapped.
    if (len(tokens)==11 and tokens[0]==('punctuation','(')
            and tokens[1]==('punctuation','(')
            and tokens[2][0] in identifier_kinds
            and tokens[3]==('operator','+')
            and tokens[4][0] in identifier_kinds
            and tokens[5]==('punctuation',')')
            and tokens[6]==('operator','+')
            and tokens[7][0] in identifier_kinds
            and tokens[8]==('punctuation',')')
            and tokens[9]==('operator','<=') and tokens[10][0]=='number'):
        return ('ATOM',(tokens[2],tokens[3],tokens[4],tokens[6],tokens[7],
                        tokens[9],tokens[10]))
    return None


def _canonical_check_atom(tokens, *, route_economics=False):
    if route_economics:
        tokens=_canonical_simple_identifier_cast_operand(tokens)
        tokens=_route_economics_catalog_tokens(tokens)
        tokens=_canonical_json_text_key_casts(tokens)
    else:
        tokens=_canonical_json_text_key_casts(tokens)
        tokens=_canonical_simple_identifier_cast_operand(tokens)
    recognized,normalized=_canonical_40_second_interval_comparison(tokens)
    if recognized:
        return normalized
    normalized=_canonical_identifier_addition_comparison(tokens)
    if normalized is not None:
        return normalized
    recognized,normalized=_canonical_in_any_atom(tokens,route_economics=route_economics)
    if recognized:
        return normalized
    return _canonical_literal_text_comparison(tokens)


def canonicalize_check_ast(node, *, route_economics=False):
    """Apply the narrow catalog-equivalence rules to a parsed CHECK AST."""
    if not isinstance(node,tuple) or len(node)!=2:
        return None
    kind,value=node
    if kind in ('AND','OR'):
        if not isinstance(value,tuple) or len(value)<2:
            return None
        children=tuple(canonicalize_check_ast(child,route_economics=route_economics) for child in value)
        if any(child is None for child in children):
            return None
        if kind=='AND':
            # AND is associative under SQL's three-valued boolean semantics;
            # flatten only same-operator nodes, preserving child order and
            # every OR subtree.
            flattened=[]
            for child in children:
                if child[0]=='AND':flattened.extend(child[1])
                else:flattened.append(child)
            children=tuple(flattened)
        return kind,children
    if kind=='IN_LIST':
        if (isinstance(value,tuple) and len(value)==2
                and isinstance(value[0],tuple) and value[0][0] in ('word','quoted_identifier')
                and isinstance(value[1],tuple) and value[1]
                and all(isinstance(member,tuple) and len(member)==2 and member[0]=='literal'
                        for member in value[1])):
            return node
        return None
    if kind=='IS_TRUE':
        if (not route_economics or not isinstance(value,tuple) or len(value)!=1):
            return None
        child=canonicalize_check_ast(value[0],route_economics=True)
        return None if child is None else ('IS_TRUE',(child,))
    if kind!='ATOM' or not isinstance(value,tuple):
        return None
    return _canonical_check_atom(value,route_economics=route_economics)


def canonical_check_expression(value, table=None, name=None, *, route_economics=False):
    """Canonicalize only Boolean grouping for CHECK constraints."""
    if not isinstance(value,str):return None
    if route_economics and (table,name) not in _ROUTE_ECONOMICS_CHECKS:
        return None
    if table=='executions' and name=='ck_executions_error_code':
        value=canonical_error_code_expression(value)
        if value is None:return None
    tokens=_check_tokens(value)
    if tokens is None or not _check_delimiters(tokens):return None
    parsed=_canonical_check_node(tokens,route_economics=route_economics,check_name=name)
    return canonicalize_check_ast(parsed,route_economics=route_economics)


def expected_columns():
    result = []
    for table in sorted(TABLES,key=lambda t:t.name):
        for i,c in enumerate(table.columns,1):
            typ = str(c.type.compile(dialect=dialect())).lower().replace('timestamp with time zone','timestamp with time zone')
            result.append((table.name,c.name,typ,not c.nullable,
                           'statement_timestamp()' if c.server_default is not None else None,i))
    return result


def expected_constraints():
    expected = {('projects','uq_projects_organization_id_id'): ('u',False,False,True,('organization_id','id'),None,None,(), ' ',' ',None)}
    for table in TABLES:
        for c in table.constraints:
            kind = 'c' if isinstance(c,CheckConstraint) else 'p' if isinstance(c,PrimaryKeyConstraint) else 'u' if isinstance(c,UniqueConstraint) else 'f'
            cols = tuple(c.columns.keys()) if kind != 'c' else ()
            target = tuple(e.target_fullname.split('.')[-1] for e in c.elements) if kind=='f' else ()
            target_table = c.elements[0].target_fullname.split('.')[-2] if kind=='f' else None
            check_expression = canonical_check_expression(str(c.sqltext),table.name,c.name) if kind == 'c' else None
            if kind == 'c':
                if check_expression is None:
                    raise ValueError('unrecognized expected CHECK constraint')
            expected[(table.name,str(c.name))] = (kind,False,False,True,cols,'public' if kind=='f' else None,
                target_table,target,'r' if kind=='f' else ' ','r' if kind=='f' else ' ',check_expression)
    return expected


def expected_indexes():
    values = {('projects','uq_projects_organization_id_id'):(True,True,True,True,True,True,'btree',('organization_id','id'),2,2)}
    for table in TABLES:
        for c in table.constraints:
            if isinstance(c,(PrimaryKeyConstraint,UniqueConstraint)):
                cols=tuple(c.columns.keys()); values[(table.name,str(c.name))]=(True,True,True,True,True,True,'btree',cols,len(cols),len(cols))
        for i in table.indexes:
            cols=tuple(c.name for c in i.columns); values[(table.name,i.name)]=(False,True,True,True,True,True,'btree',cols,len(cols),len(cols))
    return values


@contextmanager
def _validation_stage(observer, name):
    started = perf_counter()
    try:
        yield
    finally:
        if observer is not None:
            error = sys.exc_info()[1]
            try:
                observer(name, perf_counter() - started,
                         type(error).__name__ if error is not None else None)
            except Exception:
                # Diagnostic observers cannot alter validation decisions.
                pass


async def validate_product_runtime(connection, *, stage_observer=None):
    return await _validate_product_runtime(connection, stage_observer=stage_observer, successor=False)


async def validate_route_economics_product_runtime(connection, *, stage_observer=None):
    """Run the unchanged product contract against its explicit V1.3 revision gate."""
    return await _validate_product_runtime(connection, stage_observer=stage_observer, successor=True)


async def validate_usage_events_product_runtime(connection, *, stage_observer=None):
    """Run frozen product invariants at the exact V1.4B successor revision."""
    return await _validate_product_runtime(connection, stage_observer=stage_observer,
                                           successor=True, usage_events=True)


async def _validate_product_runtime(connection, *, stage_observer=None, successor=False,
                                    usage_events=False):
    try:
        with _validation_stage(stage_observer, 'FOUNDATION'):
            foundation = (validate_usage_events_foundation if usage_events else
                          validate_route_economics_foundation if successor else validate_product_foundation)
            await foundation(connection)
        async with catalog_resolution(connection):
            with _validation_stage(stage_observer, 'PRODUCT_RLS_ENCODING'):
                if await connection.scalar(text("SELECT pg_catalog.current_setting('server_encoding') = 'UTF8' AND (SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relname IN ('tasks','executions') AND c.relkind='r' AND c.relrowsecurity AND c.relforcerowsecurity) = 2")) is not True:
                    raise ValueError()
            with _validation_stage(stage_observer, 'COLUMNS'):
                columns = [tuple(row) for row in (await connection.execute(text(COLUMNS_SQL))).all()]
                if columns != expected_columns(): raise ValueError()
            with _validation_stage(stage_observer, 'CONSTRAINTS'):
                actual={}
                for table,name,kind,defer,deferred,valid,cols,ns,target,tcols,update,delete,sql in (await connection.execute(text(CONSTRAINTS_SQL))).all():
                    # CHECK column dependencies are redundant with the exact frozen
                    # expression; PostgreSQL discovers those independently.
                    check_expression = canonical_check_expression(sql,table,name) if kind=='c' else None
                    actual[(table,name)]=(kind,defer,deferred,valid,tuple(cols or ()) if kind!='c' else (),ns,target,tuple(tcols or ()),update,delete,check_expression)
                if actual != expected_constraints(): raise ValueError()
            with _validation_stage(stage_observer, 'INDEXES'):
                indexes={}
                for table,name,*row in (await connection.execute(text(INDEXES_SQL))).all():
                    row[7]=tuple(row[7]); indexes[(table,name)]=tuple(row)
                if indexes != expected_indexes(): raise ValueError()
            with _validation_stage(stage_observer, 'POLICIES'):
                def policy_ast(value,name):
                    if value is None:return None
                    result=canonical_policy_expression(value,policy_name=name)
                    if result is None:raise ValueError()
                    return result
                policy_rows={}
                for table,name,cmd,permissive,roles,using,check in (await connection.execute(text(POLICIES_SQL))).all():
                    policy_rows[name]=(table,cmd,permissive,tuple(roles),
                        policy_ast(using,name),policy_ast(check,name))
                expected={}
                for name,(table,cmd,sql) in POLICIES.items():
                    policy_ast=canonical_policy_expression(sql,policy_name=name)
                    if policy_ast is None:
                        raise ValueError()
                    expected[name]=(table,'r' if cmd=='SELECT' else 'a',True,('jous_runtime',),
                                    policy_ast if cmd=='SELECT' else None,
                                    policy_ast if cmd=='INSERT' else None)
                if policy_rows != expected: raise ValueError()
            # ACL sources, grant options, table-level grants and inherited/public
            # privileges are rejected in addition to effective column checks.
            with _validation_stage(stage_observer, 'ACL_TABLE_PRIVILEGES'):
                safe = await connection.scalar(text("""SELECT NOT EXISTS (
              SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace,
              LATERAL pg_catalog.aclexplode(COALESCE(c.relacl,pg_catalog.acldefault('r',c.relowner))) a
              WHERE n.nspname='public' AND c.relname IN ('tasks','executions') AND a.grantee<>c.relowner)
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              JOIN pg_catalog.pg_attribute x ON x.attrelid=c.oid,
              LATERAL pg_catalog.aclexplode(x.attacl) a
              WHERE n.nspname='public' AND c.relname IN ('tasks','executions') AND
              (a.is_grantable OR a.grantee NOT IN (c.relowner,(SELECT oid FROM pg_catalog.pg_roles WHERE rolname='jous_runtime'))))
              AND NOT EXISTS (SELECT 1 FROM (VALUES ('tasks'),('executions')) t(name)
              CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(name)
              CROSS JOIN (VALUES ('UPDATE'),('DELETE'),('TRUNCATE'),('REFERENCES'),('TRIGGER')) p(priv)
                  WHERE pg_catalog.has_table_privilege(CAST(r.name AS pg_catalog.name),'public.'||t.name,p.priv))"""))
                if safe is not True: raise ValueError()
            with _validation_stage(stage_observer, 'COLUMN_PRIVILEGES'):
                privileges=(await connection.execute(text("""SELECT c.relname,a.attname,r.name,p.priv,
              pg_catalog.has_column_privilege(CAST(r.name AS pg_catalog.name),c.oid,a.attnum,p.priv)
              FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              JOIN pg_catalog.pg_attribute a ON a.attrelid=c.oid
              CROSS JOIN (VALUES ('jous_runtime'),('jous_security_reader')) r(name)
              CROSS JOIN (VALUES ('SELECT'),('INSERT'),('UPDATE'),('REFERENCES')) p(priv)
                  WHERE n.nspname='public' AND c.relname IN ('tasks','executions') AND a.attnum>0 AND NOT a.attisdropped"""))).all()
                if len(privileges) != (len(TASK_COLUMNS)+len(EXECUTION_COLUMNS))*8: raise ValueError()
                for table,col,role,priv,value in privileges:
                    expected=role=='jous_runtime' and (priv=='SELECT' or priv=='INSERT' and col not in ('created_at','recorded_at'))
                    if value is not expected: raise ValueError()
    except Exception:
        raise DatabaseUnavailable('Product database safety check failed') from None
