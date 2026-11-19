"""Fail-closed canonicalization for V1.2 product-policy catalog expressions.

Only PostgreSQL renderings proven by the managed executions INSERT and
tasks INSERT policy fixtures are folded. This parser is deliberately a
small grammar for source-owned V1.2 policy expressions, not a general SQL
normalizer.
"""
import re


UUID_PATTERN = "'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'"


class _PolicySyntaxError(ValueError):
    pass


def _tokens(source):
    if not isinstance(source,str):
        return None
    result=[];i=0
    multi=('::','>=','<=','<>','!=')
    while i<len(source):
        ch=source[i]
        if ch.isspace():
            i+=1;continue
        if ch=="'":
            start=i;i+=1
            while i<len(source):
                if source[i]=="'":
                    if i+1<len(source) and source[i+1]=="'":i+=2;continue
                    i+=1;break
                if source[i]=='\\':i+=2;continue
                i+=1
            else:return None
            result.append(('literal',source[start:i]));continue
        if ch=='"':
            start=i;i+=1
            while i<len(source):
                if source[i]=='"':
                    if i+1<len(source) and source[i+1]=='"':i+=2;continue
                    i+=1;break
                i+=1
            else:return None
            result.append(('identifier',source[start:i]));continue
        if ch.isalpha() or ch=='_' or ord(ch)>=128:
            start=i;i+=1
            while i<len(source) and (source[i].isalnum() or source[i] in '_$' or ord(source[i])>=128):i+=1
            result.append(('word',source[start:i]));continue
        if ch.isdigit():
            start=i;i+=1
            while i<len(source) and source[i].isdigit():i+=1
            result.append(('number',source[start:i]));continue
        operator=next((value for value in multi if source.startswith(value,i)),None)
        if operator:
            result.append(('operator',operator));i+=len(operator);continue
        if ch in '=~<>':
            result.append(('operator',ch));i+=1;continue
        if ch in '().,[]':
            result.append(('punctuation',ch));i+=1;continue
        return None
    return result


class _Parser:
    def __init__(self,tokens):
        self.tokens=tokens
        self.position=0

    def peek(self,kind=None,value=None):
        if self.position>=len(self.tokens):return False
        token=self.tokens[self.position]
        return ((kind is None or token[0]==kind) and
                (value is None or token[1].upper()==value.upper()))

    def take(self,kind=None,value=None):
        if not self.peek(kind,value):raise _PolicySyntaxError('unexpected token')
        token=self.tokens[self.position];self.position+=1
        return token

    def word(self,value):
        if self.peek('word',value):self.position+=1;return True
        return False

    def punctuation(self,value):
        return self.peek('punctuation',value)

    def require_punctuation(self,value):
        self.take('punctuation',value)

    def parse(self):
        result=self.parse_or()
        if self.position!=len(self.tokens):raise _PolicySyntaxError('unconsumed input')
        return result

    def parse_or(self):
        children=[self.parse_and()]
        while self.word('OR'):children.append(self.parse_and())
        return ('OR',tuple(children)) if len(children)>1 else children[0]

    def parse_and(self):
        children=[self.parse_predicate()]
        while self.word('AND'):children.append(self.parse_predicate())
        return ('AND',tuple(children)) if len(children)>1 else children[0]

    def parse_predicate(self):
        if self.word('EXISTS'):
            self.require_punctuation('(')
            self.take('word','SELECT')
            selected=self.parse_scalar()
            self.take('word','FROM')
            relation=self.parse_name()
            alias=self.take('word')[1]
            self.take('word','WHERE')
            condition=self.parse_or()
            self.require_punctuation(')')
            return ('EXISTS',selected,relation,alias,condition)

        left=self.parse_scalar()
        if self.word('IS'):
            negated=self.word('NOT')
            self.take('word','NULL')
            return ('IS_NULL',left,negated)
        if self.word('IN'):
            self.require_punctuation('(')
            values=[self.parse_scalar()]
            while self.punctuation(','):
                self.require_punctuation(',');values.append(self.parse_scalar())
            self.require_punctuation(')')
            return ('IN',left,tuple(values))
        if self.word('OPERATOR'):
            self.require_punctuation('(')
            schema=self.take('word')[1]
            self.require_punctuation('.')
            operator=self.take('operator')[1]
            self.require_punctuation(')')
            if (schema,operator)!=('pg_catalog','~'):
                raise _PolicySyntaxError('unsupported OPERATOR')
        elif self.peek('operator') and self.tokens[self.position][1] in ('=','<>','!=','<','<=','>','>=','~'):
            operator=self.take('operator')[1]
        else:
            if (isinstance(left,tuple) and
                    (left[0] in ('AND','OR','EXISTS','IS_NULL','COMPARE') or
                     (len(left)==3 and left[0]=='CALL'
                      and left[1]==('jous_security','organization_is_active')
                      and len(left[2])==1))):
                return left
            # Policy predicates in the source contract are comparisons,
            # NULL tests, IN lists, Boolean combinations, or EXISTS.
            raise _PolicySyntaxError('unsupported predicate')
        right=self.parse_scalar()
        left,right=self._normalize_proven_comparison(operator,left,right)
        return ('COMPARE',operator,left,right)

    @staticmethod
    def _is_tasks_role_array(node):
        return node == ('CALL',('ANY',),(
            ('CAST',('ARRAY',(
                ('CAST',('LITERAL',"'owner'"),('character','varying')),
                ('CAST',('LITERAL',"'member'"),('character','varying')),
            )),('text','[]')),
        ))

    @staticmethod
    def _is_current_setting(node,key):
        return node==('CALL',('current_setting',),
                      (('LITERAL',f"'jous.{key}'"),('BOOLEAN',True)))

    @staticmethod
    def _is_context_setting_cast(node):
        return (isinstance(node,tuple) and len(node)==3 and node[0]=='CAST'
                and node[2]==('uuid',)
                and any(_Parser._is_current_setting(node[1],key)
                        for key in ('user_id','organization_id')))

    @staticmethod
    def _text_literal(node,value):
        if node==('LITERAL',value):return True
        return (isinstance(node,tuple) and len(node)==3 and node[0]=='CAST'
                and node[1]==('LITERAL',value) and node[2]==('text',))

    @staticmethod
    def _normalize_proven_comparison(operator,left,right):
        if (operator=='~' and any(_Parser._is_current_setting(left,key)
                        for key in ('user_id','organization_id'))
                and _Parser._text_literal(right,UUID_PATTERN)):
            right=('LITERAL',UUID_PATTERN)
        if (operator=='=' and isinstance(left,tuple) and left[:1]==('IDENTIFIER',)
                and left[1] in (('m','status'),('u','status'),('p','status'))
                and _Parser._text_literal(right,"'active'")):
            right=('LITERAL',"'active'")
        if (operator=='=' and left==('IDENTIFIER',('m','role'))
                and _Parser._text_literal(right,"'owner'")):
            left=('IDENTIFIER',('m','role'));right=('LITERAL',"'owner'")
        if (operator=='=' and isinstance(left,tuple) and left[:1]==('CAST',)
                and len(left)==3 and left[1]==('IDENTIFIER',('m','status'))
                and left[2]==('text',) and _Parser._text_literal(right,"'active'")):
            left=left[1];right=('LITERAL',"'active'")
        if (operator=='=' and isinstance(left,tuple) and left[:1]==('CAST',)
                and len(left)==3 and left[1] in (('IDENTIFIER',('u','status')),
                                                  ('IDENTIFIER',('p','status')))
                and left[2]==('text',) and _Parser._text_literal(right,"'active'")):
            left=left[1];right=('LITERAL',"'active'")
        if (operator=='=' and isinstance(left,tuple) and left[:1]==('CAST',)
                and left[1:]==(('IDENTIFIER',('m','role')),('text',))
                and _Parser._text_literal(right,"'owner'")):
            left=('IDENTIFIER',('m','role'));right=('LITERAL',"'owner'")
        return left,right

    def parse_scalar(self):
        value=self.parse_primary()
        while self.peek('operator','::'):
            self.take('operator','::')
            value=self._cast(value,self.parse_type_name())
        return value

    @staticmethod
    def _cast(value,type_name):
        # Fold the observed CAST(... AS pg_catalog.uuid) spelling only for
        # the proven user/organization context-setting expressions.
        if (any(_Parser._is_current_setting(value,key)
                        for key in ('user_id','organization_id'))
                and type_name==('pg_catalog','uuid')):
            type_name=('uuid',)
        return ('CAST',value,type_name)

    def parse_primary(self):
        if self.word('CAST'):
            self.require_punctuation('(')
            value=self.parse_scalar()
            self.take('word','AS')
            type_name=self.parse_name()
            self.require_punctuation(')')
            return self._cast(value,type_name)
        if self.word('CASE'):
            self.take('word','WHEN')
            condition=self.parse_or()
            self.take('word','THEN')
            then_value=self.parse_scalar()
            self.take('word','ELSE')
            else_value=self.parse_scalar()
            self.take('word','END')
            if (self._is_context_setting_cast(then_value)
                    and (else_value==('NULL',) or
                         else_value==('CAST',('NULL',),('uuid',)))):
                else_value=('TYPED_NULL',('uuid',))
            return ('CASE',condition,then_value,else_value)
        if self.punctuation('('):
            self.require_punctuation('(')
            scalar_start=self.position
            try:
                value=self.parse_scalar()
                if self.punctuation(')'):
                    self.require_punctuation(')')
                    return value
            except _PolicySyntaxError:
                pass
            self.position=scalar_start
            value=self.parse_or()
            self.require_punctuation(')')
            return value
        if self.word('ARRAY'):
            self.require_punctuation('[')
            values=[]
            if not self.punctuation(']'):
                values.append(self.parse_scalar())
                while self.punctuation(','):
                    self.require_punctuation(',');values.append(self.parse_scalar())
            self.require_punctuation(']')
            return ('ARRAY',tuple(values))
        if self.peek('literal'):
            return ('LITERAL',self.take('literal')[1])
        if self.peek('number'):
            return ('NUMBER',self.take('number')[1])
        if self.word('NULL'):return ('NULL',)
        if self.word('TRUE'):return ('BOOLEAN',True)
        if self.word('FALSE'):return ('BOOLEAN',False)
        if self.peek('word') or self.peek('identifier'):
            name=self.parse_name()
            if self.punctuation('('):
                self.require_punctuation('(')
                args=[]
                if not self.punctuation(')'):
                    args.append(self.parse_scalar())
                    while self.punctuation(','):
                        self.require_punctuation(',');args.append(self.parse_scalar())
                self.require_punctuation(')')
                if name in (('pg_catalog','length'),('length',)):
                    name=('length',)
                elif name in (('pg_catalog','current_setting'),('current_setting',)):
                    name=('current_setting',)
                    if (len(args)==2 and args[0][0:1]==('CAST',)
                            and args[0][2:]==(('text',),)
                            and args[1]==('BOOLEAN',True)
                            and args[0][1] in (('LITERAL',"'jous.user_id'"),
                                               ('LITERAL',"'jous.organization_id'"))):
                        args[0]=args[0][1]
                elif name==('ANY',):
                    name=('ANY',)
                return ('CALL',name,tuple(args))
            folded=tuple(part.lower() for part in name)
            return ('IDENTIFIER',folded)
        raise _PolicySyntaxError('unsupported scalar')

    def parse_name(self):
        first=self.take('word')
        parts=[first[1]]
        while self.punctuation('.'):
            self.require_punctuation('.')
            parts.append(self.take('word')[1])
        return tuple(parts)

    def parse_type_name(self):
        name=self.parse_name()
        if name[-1]=='character' and self.peek('word','varying'):
            name=name+ (self.take('word')[1].lower(),)
        if self.punctuation('['):
            self.require_punctuation('[');self.require_punctuation(']')
            name=name+('[]',)
        return name


def canonical_policy_expression(source, *, policy_name=None):
    """Return a complete V1.2 policy AST; reject absent or unsupported input.

    Absence is represented only by the caller, which knows whether a policy
    clause is actually NULL. A supplied expression must never collapse to
    the same value as an absent clause.
    """
    tokens=_tokens(source)
    if tokens is None or not tokens:
        raise _PolicySyntaxError('policy expression is absent or unsupported')
    try:
        result=_Parser(tokens).parse()
        # Fold only the observed source IN and catalog typed-ANY forms for
        # the owner/member admission predicate in tasks policies. The ordered
        # values, varchar element casts, text[] result cast, and m.role
        # operand are all checked by exact AST shape.
        if policy_name in ('jous_tasks_insert','jous_tasks_select'):
            result=_normalize_tasks_role_members(result)
            result=_normalize_tasks_target_qualification(result,policy_name)
        # pg_get_expr drops the target-table qualifier from this one
        # top-level check expression. Keep the same relation-qualified AST
        # as the source, and do not rewrite correlated subquery references.
        if (policy_name=='jous_executions_insert' and isinstance(result,tuple)
                and len(result)==2 and result[0]=='AND' and result[1]
                and result[1][0][0]=='COMPARE' and result[1][0][1]=='='
                and result[1][0][2]==('IDENTIFIER',('actor_user_id',))):
            children=list(result[1]);comparison=list(children[0])
            comparison[2]=('IDENTIFIER',('executions','actor_user_id'))
            children[0]=tuple(comparison);result=('AND',tuple(children))
        return result
    except _PolicySyntaxError:
        raise


def _normalize_tasks_role_members(node):
    if not isinstance(node,tuple):
        return node
    if len(node)==3 and node[0]=='IN' and node[1]==('IDENTIFIER',('m','role')):
        values=node[2]
        if values==(('LITERAL',"'owner'"),('LITERAL',"'member'")):
            return ('TASK_ROLE_MEMBERS',node[1],("'owner'","'member'"))
    if (len(node)==4 and node[0]=='COMPARE' and node[1]=='='
            and node[2]==('CAST',('IDENTIFIER',('m','role')),('text',))
            and _Parser._is_tasks_role_array(node[3])):
        return ('TASK_ROLE_MEMBERS',('IDENTIFIER',('m','role')),
                ("'owner'","'member'"))
    return tuple(_normalize_tasks_role_members(item) if isinstance(item,tuple) else item
                 for item in node)


def _normalize_tasks_target_qualification(node,policy_name):
    """Normalize only deparsed target references at policy-specific root positions.

    Managed tasks policies drop target qualification only at observed root
    positions. Correlated references inside EXISTS remain relation-qualified.
    """
    expected_count={'jous_tasks_select':5,'jous_tasks_insert':7}.get(policy_name)
    if not (isinstance(node,tuple) and len(node)==2 and node[0]=='AND'
            and len(node[1])==expected_count):
        return node
    children=list(node[1])
    first=children[0]
    if (isinstance(first,tuple) and len(first)==4 and first[0]=='COMPARE'
            and first[1]=='=' and first[2]==('IDENTIFIER',('tasks','organization_id'))):
        first=list(first);first[2]=('IDENTIFIER',('organization_id',));children[0]=tuple(first)
    helper=children[1]
    if (isinstance(helper,tuple) and helper==('CALL',('jous_security','organization_is_active'),
                                             (('IDENTIFIER',('tasks','organization_id')),))):
        children[1]=('CALL',('jous_security','organization_is_active'),
                     (('IDENTIFIER',('organization_id',)),))
    if policy_name=='jous_tasks_insert':
        last=children[6]
        if (isinstance(last,tuple) and len(last)==4 and last[0]=='COMPARE'
                and last[1]=='=' and last[2]==('IDENTIFIER',('tasks','actor_user_id'))):
            last=list(last);last[2]=('IDENTIFIER',('actor_user_id',));children[6]=tuple(last)
    return ('AND',tuple(children))
