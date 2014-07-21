import hashlib
import operator
import itertools

import vstruct
import envi.bits as e_bits

from vivisect.symboliks.constraints import *

def evalSymbolik(reprstr):
    '''
    Take a previously repr'd symboliks object and eval it
    back into objecthood.

    Example:
        x = "o_add(Var('eax', 4), 3)"
        symobj = evalSymbolik(x)
    '''
    return eval(reprstr, globals(), {})

class ExpressionHelper:

    def __init__(self):
        self.d = {}
        self.d['mem'] = self

    def parseExpression(self, expr):
        ret = eval(expr, globals(), self)
        if type(ret) in (int, long):
            return Const(ret)
        return ret

    def __getitem__(self, name):
        r = self.d.get(name)
        if r != None:
            return r
        #return Var(name)

    def __getslice__(self, symaddr, symsize):
        return Mem(symaddr, symsize)

    def __call__(self, symaddr, symsize):
        return Mem(symaddr, symsize)

t = ExpressionHelper()
def exprSymbolik(expr):
    return t.parseExpression(expr)

def frobSymbol(thing, width):
    '''
    Translate native python types to symbolik types
    if we know how...
    '''
    ttype = type(thing)
    if ttype in (long, int):
        return Const(thing, width)

    if ttype in (str,): # Unicode?
        return exprSymbolik(thing)

    return thing

def getSymbolikImport(vw, impname):
    '''
    Resolve (hopefully) and return a symbolik import emulation
    function for the given import by name.
    '''
    modbase = vw.getMeta('SymbolikImportEmulation')
    if modbase == None:
        return None

    nameparts = impname.split('.')

    # FIXME *.malloc!
    # FIXME cache

    mod = vw.loadModule(modbase)
    return vstruct.resolve(mod, nameparts)

class SymbolikBase:
    idgen = itertools.count()
    def __init__(self):
        self._sym_id       = self.idgen.next()
        self._solve_cache  = None
        self._reduced      = False
        self._walk_tags    = {}
        self._strval       = ''
        self.kids          = []

    def __add__(self, other):
        return o_add(self, other, self.getWidth())

    def __iadd__(self, other):
        return o_add(self, other, self.getWidth())

    def __sub__(self, other):
        return o_sub(self, other, self.getWidth())

    def __isub__(self, other):
        return o_sub(self, other, self.getWidth())

    def __xor__(self, other):
        return o_xor(self, other, self.getWidth())

    def __ixor__(self, other):
        return o_xor(self, other, self.getWidth())

    def __lshift__(self, count):
        return o_lshift(self, count, self.getWidth())

    def __ilshift__(self, count):
        return o_lshift(self, count, self.getWidth())

    def __rshift__(self, count):
        return o_rshift(self, count, self.getWidth())

    def __irshift__(self, count):
        return o_rshift(self, count, self.getWidth())

    def __or__(self, other):
        return o_or(self, other, self.getWidth())

    def __ior__(self, other):
        return o_or(self, other, self.getWidth())

    def __and__(self, other):
        return o_and(self, other, self.getWidth())

    def __iand__(self, other):
        return o_and(self, other, self.getWidth())

    def __mod__(self, other):
        return o_mod(self, other, self.getWidth())

    def __imod__(self, other):
        return o_mod(self, other, self.getWidth())

    def __mul__(self, other):
        return o_mul(self, other, self.getWidth())

    def __imul__(self, other):
        return o_mul(self, other, self.getWidth())

    def __div__(self, other):
        return o_div(self, other, self.getWidth())

    def __idiv__(self, other):
        return o_div(self, other, self.getWidth())

    def __pow__(self, other):
        return o_pow(self, other, self.getWidth())

    def __hash__(self):
        return hash(self.solve())

    def __eq__(self, other):

        if other == None:
            return False

        if type(other) in (int, long):
            return self.solve() == other

        return self.solve() == other.solve()

    def __ne__(self, other):
        return not self.__eq__(other)

    def _clearCache(self, symbase, ctx):
        symbase._solved_cache = None
        symbase._reduced      = False
        symbase._walk_tags     = {}
        symbase._strval       = ""

    def clearCache(self):
        self.walkTree(cb=self._clearCache)

    # FIXME more comparitors!
    def solve(self, emu=None):
        '''
        Produce a reproducable answer based on the current state if provided.
        '''
        if self._solve_cache != None:
            return self._solve_cache
        self._solve_cache = self._solve(emu=emu)
        return self._solve_cache

    def _solve(self, emu=None):
        '''
        Produce a reproducable answer based on the current state if provided.
        '''
        raise Exception('%s *must* implement solve(emu=emu)!' % self.__class__.__name__)

    def reduce(self, emu=None):
        '''
        Algebraic reduction and operator folding where possible. (INLINE!)
        '''
        if self._reduced:
            return self

        child = self._reduce(emu=emu)
        child._reduced = True
        return child

    def _reduce(self, emu=None):
        '''
        Algebraic reduction and operator folding where possible. (INLINE!)
        '''
        raise Exception('%s *must* implement reduce(emu=emu)!' % self.__class__.__name__)

    def update(self, emu):
        '''
        Return an updated representation for this symbolik state based on the given
        emulator.  This is *NOT* inline.
        '''
        raise Exception('%s *must* implement update(emu)!' % self.__class__.__name__)

    def isDiscrete(self, emu=None):
        '''
        Returns True if the given symbolik (from here down) does *not* depend on
        any variables or runtime values.
        '''
        raise Exception('Symbolik %s *must* implement isDiscrete(emu=emu)!' % self.__class__.__name__)

    def walkTree(self, cb, ctx=None, walktag=None):

        if walktag and self._walk_tags.get(walktag) or not len(self.kids):
            return

        # when kids[i] is a list of tupes then we need to call into it!
        for i in range(len(self.kids)):
            self.kids[i].walkTree(cb, ctx=ctx, walktag=walktag)

        clearedCache = False
        for i in range(len(self.kids)):
            oldkid = self.kids[i]
            newkid = cb(oldkid, ctx)
            self.kids[i] = newkid
            if hasattr(oldkid, '_sym_id') and hasattr(newkid, '_sym_id') and oldkid._sym_id != newkid._sym_id:
                self._clearCache(self, None)
                clearedCache = True

        if not clearedCache:
            self._walk_tags[ walktag ] = 1

    # FIXME getVars() method!

class cnot(SymbolikBase):
    '''
    Mostly used to wrap the reverse of a contraint which is based on
    a variable.
    '''
    def __init__(self, v1):
        SymbolikBase.__init__(self)
        self.kids.append(v1)

    def __repr__(self):
        return 'cnot( %s )' % (repr(self.kids[0]))

    def __str__(self):
        return 'cnot(%s)' % str(self.kids[0])

    def _solve(self, emu=None):
        return int( not bool( self.kids[0].solve(emu=emu)) )

    def isDiscrete(self, emu=None):
        return self.kids[0].isDiscrete(emu=emu)

    def update(self, emu):
        # FIXME dependancy loop...
        from vivisect.symboliks.constraints import Constraint
        v1 = self.kids[0].update(emu=emu)
        if isinstance(v1, Constraint):
            return v1.reverse()
        return cnot(v1)

    def _reduce(self, emu=None):
        # FIXME dependancy loop...
        from vivisect.symboliks.constraints import Constraint
        self.kids[0] = self.kids[0].reduce(emu=emu)
        if isinstance( self.kids[0], Constraint):
            return self.kids[0].reverse()
        if isinstance( self.kids[0], cnot):
            return self.kids[0].kids[0]
        return self

    def getWidth(self):
        return self.kids[0].getWidth()

class Call(SymbolikBase):
    '''
    This represents the return value of an instance of a call to
    a function.
    '''
    def __init__(self, funcsym, width, argsyms=[]):
        SymbolikBase.__init__(self)
        self.width = width
        self.kids = [funcsym]
        self.kids.extend(argsyms)

    def getWidth(self):
        return self.width

    def __str__(self):
        if self._strval:
            return self._strval
        args = ','.join( [ str(sym) for sym in self.kids[1:]] )
        self._strval = '%s(%s)' % (self.kids[0], args)
        return self._strval

    def __repr__(self):
        return 'Call(%s, argsyms=%s)' % (repr(self.kids[0]), repr(self.kids[1:]))

    def _reduce(self, emu=None):
        self._strval = ''
        self.kids[0] = self.kids[0].reduce(emu=emu)
        self.kids[1:] = [ x.reduce(emu=emu) for x in self.kids[1:] ]
        return self

    def _solve(self, emu=None):
        sbase = self.kids[0].solve(emu=emu)
        for arg in self.kids[1:]:
            sbase ^= arg.solve(emu=emu)
        return sbase

    def update(self, emu):
        self._strval = ''
        self.kids[0] = self.kids[0].update(emu)
        self.kids[1:] = [ x.update(emu) for x in self.kids[1:] ]
        return Call(self.kids[0], self.width, self.kids[1:])

    def isDiscrete(self, emu=None):
        # FIXME resolve for the function!  it could be!
        return False

class Mem(SymbolikBase):
    '''
    This is effectivly a cop-out for symbolic states read in from
    memory which has not been initialized yet.
    '''
    def __init__(self, symaddr, symsize):
        SymbolikBase.__init__(self)
        self.kids = [symaddr, symsize]

    def __repr__(self):
        return 'Mem(%s, %s)' % (repr(self.kids[0]), repr(self.kids[1]))

    def __str__(self):
        if self._strval:
            return self._strval

        self._strval = 'mem[%s:%s]' % (str(self.kids[0]), str(self.kids[1]))
        return self._strval

    def _reduce(self, emu=None):
        self._strval = ''
        self.kids[0] = self.kids[0].reduce(emu=emu)
        self.kids[1] = self.kids[1].reduce(emu=emu)
        return self

    def update(self, emu):
        self._strval = ''
        symaddr = self.kids[0].update(emu)
        symsize = self.kids[1].update(emu)

        # If the emulator (or is viv) knows about us, update to his...
        ret = emu.readSymMemory(symaddr, symsize)
        if ret != None:
            return ret

        return Mem(symaddr, symsize)

    def isDiscrete(self, emu=None):
        # non-updated memory locations are *never* discrete
        return False

    def _solve(self, emu=None):
        addrval = self.kids[0].solve(emu=emu)
        sizeval = self.kids[1].solve(emu=emu)
        # FIXME higher entropy!
        return hash(str(addrval)) & 0xffffffff

    def getWidth(self):
        # FIXME should we do something about that?
        return self.kids[1].solve()

class Var(SymbolikBase):

    def __init__(self, name, width):
        SymbolikBase.__init__(self)
        self.name  = name
        self.width = width
        self.mask = e_bits.u_maxes[width]

    def __repr__(self):
        return 'Var("%s", width=%d)' % (self.name, self.width)

    def __str__(self):
        if self._strval:
            return self._strval
        self._strval = self.name
        return self._strval

    def _solve(self, emu=None):
        name = self.name
        if emu != None:
            # Is this really the only one that uses the emu?
            name += emu.getRandomSeed()
        return hash(hashlib.md5(name).hexdigest()) & self.mask

    def update(self, emu):
        ret = emu.getSymVariable(self.name, create=False)
        if ret != None:
            return ret
        return Var(self.name, width=self.width)

    def _reduce(self, emu=None):
        return self

    def getWidth(self):
        return self.width

    def isDiscrete(self, emu=None):
        return False

class Arg(SymbolikBase):
    '''
    An "Arg" is a special kind of variable used to facilitate cross
    function boundary solving.
    '''
    def __init__(self, idx, width):
        SymbolikBase.__init__(self)
        self.idx = idx
        self.width = width
        self.mask = e_bits.u_maxes[width]

    def __repr__(self):
        return 'Arg(%d,width=%d)' % (self.idx, self.width)

    def __str__(self):
        if self._strval:
            return self._strval

        self._strval = 'arg%d' % self.idx
        return self._strval

    def _solve(self, emu=None):
        name = 'arg%d' % self.idx

        if emu != None:
            name += emu.getRandomSeed()

        return hash(hashlib.md5(name).hexdigest()) & self.mask

    def update(self, emu):
        return Arg(self.idx, width=self.width)

    def _reduce(self, emu=None):
        return self

    def getWidth(self):
        return self.width

    def isDiscrete(self, emu=None):
        return False

class Const(SymbolikBase):

    def __init__(self, value, width):
        SymbolikBase.__init__(self)
        self.width = width
        self.value = value % (2**(self.width*8))

    def _solve(self, emu=None):
        return self.value

    def _reduce(self, emu=None):
        return self

    def __repr__(self):
        return 'Const(0x%.8x)' % (self.value)

    def __str__(self):
        if self._strval:
            return self._strval

        if self.value > 4096:
            self._strval = '0x%.8x' % self.value
            return self._strval
        self._strval = str(self.value)
        return self._strval

    def getWidth(self):
        return self.width

    def update(self, emu):
        # const's are immutable... don't copy...
        return self

    def isDiscrete(self, emu=None):
        return True

class Operator(SymbolikBase):
    '''
    A class representing an algebraic operator being carried out on two
    symboliks.
    '''
    revclass = None
    oper = None
    operstr = None
    def __init__(self, v1, v2, width):
        SymbolikBase.__init__(self)

        # prevent type propagation errors early on
        if (not isinstance(v1, SymbolikBase) and
            not isinstance(v1, Constraint)):
            raise TypeError('not a symbolik(v1): %s' % v1.__class__.__name__)

        if (not isinstance(v2, SymbolikBase) and
            not isinstance(v2, Constraint)):
            raise TypeError('not a symbolik(v2): %s' % v2.__class__.__name__)

        self.width = width
        self.mod = e_bits.u_maxes[width] + 1
        self.kids = [v1, v2]

    def getWidth(self):
        return self.width

    def isConstOrAddSub(self, op):
        '''
        checks if the operator is a Const, o_add, or o_sub.  if the op is
        o_add or o_sub, checks that one of the kids is a const.
        '''
        if op.isDiscrete():
            return True

        if isinstance(op, o_add) or isinstance(op, o_sub):
            if op.kids[0].isDiscrete() or op.kids[1].isDiscrete():
                return True

        return False

    def getConstKid(self, op):
        found = None
        if op.isDiscrete():
            return op

        if op.kids[0].isDiscrete():
            found = op.kids[0]

        if op.kids[1].isDiscrete():
            if found != None:
                raise Exception('we should not have 2 consts in here')
            found = op.kids[1]

        return found

    def getConstKids(self, op1, op2):
        '''
        subtraction is NOT commutative, the order of the ops you pass matters.
        '''
        return self.getConstKid(op1), self.getConstKid(op2)

    def getNonConstKid(self, op):
        '''
        gets the first non-const kid.
        '''
        if isinstance(op, Const):
            return None

        if not op.kids[0].isDiscrete():
            return op.kids[0]

        if not op.kids[1].isDiscrete():
            return op.kids[1]

        return None

    def getNonConstKids(self, op1, op2):
        nckid0 = self.getNonConstKid(op1)
        nckid1 = self.getNonConstKid(op2)

        return nckid0, nckid1

    def _reduce(self, emu=None):
        self._strval = ''

        v1 = self.kids[0].reduce(emu=emu)
        v2 = self.kids[1].reduce(emu=emu)

        v1val = v1.solve(emu=emu)
        v2val = v2.solve(emu=emu)

        if v1.isDiscrete() and v2.isDiscrete():
            return Const(self.solve(emu=emu), self.width)

        ret = self._op_reduce(v1, v1val, v2, v2val, emu)
        if ret != None:
            return ret

        self.kids[0] = v1
        self.kids[1] = v2
        return self

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        # Override this to do per operator special reduction
        return None

    def update(self, emu):
        v1 = self.kids[0].update(emu)
        v2 = self.kids[1].update(emu)
        return self.__class__(v1, v2, self.width)

    def _solve(self, emu=None):
        v1 = self.kids[0].solve(emu=emu)
        v2 = self.kids[1].solve(emu=emu)
        return self.oper(v1, v2) % self.mod

    def isDiscrete(self, emu=None):
        return self.kids[0].isDiscrete(emu=emu) and self.kids[1].isDiscrete(emu=emu)

    def __repr__(self):
        return '%s(%s, %s)' % (self.__class__.__name__, repr(self.kids[0]), repr(self.kids[1]))

    def __str__(self):
        if self.operstr == None:
            raise Exception('Operators *must* set operstr')
        if self._strval:
            return self._strval
        elif (hasattr(self.kids[0], '_strval') and
                hasattr(self.kids[1], '_strval') and
                self.kids[0]._strval and
                self.kids[1]._strval):
            self._strval = '(%s %s %s)' % (self.kids[0]._strval, self.operstr, self.kids[1]._strval)
            return self._strval

        self._strval = '(%s %s %s)' % (str(self.kids[0]), self.operstr, str(self.kids[1]))
        return self._strval


def handle_zero_in_leaf(self, v1, v1val, v2, v2val):
    '''
    if one of the kids is 0 for an add operation, we can ignore the value.
    if one of the kids is 0 for a sub operation, we can ignore the value only
    if v2val is the one that is 0 since it does not affect the add/sub
    operation. fex, 0 - bar != bar, but bar - 0 = bar.
    '''
    if isinstance(self, o_add) and v1val == 0:
        return v2

    if v2val == 0:
        return v1

    return None

def handle_zero_in_leaf_from_parent(self, v1, v1val, v2, v2val):
    '''
    this handles the situation described above where v1val is the value that
    is zero in a subtraction operation.
    if we have a 0 +/- x term combined with anything, the 0 can be dropped.
    it MUST be combined with something, because otherwise you get into the
    same situation as the previous comment. (0-bar != bar)
    (foo - (0 - bar)) => foo + bar
    (foo + (0 - bar)) => foo - bar

    we do NOT reduce if the (0 - foo) term is on the left side of a
    subtraction, ie:
    (0 - foo) - bar
    (0 - foo) +/- (0 - bar)
    '''

    # do we have zero's as the first terms in either of v2's kids?
    if (isinstance(v2, o_sub) and
        v2.kids[0].isDiscrete() and
        v2.kids[0].solve() == 0):

        if isinstance(self, o_add):
            return o_sub(v1, v2.kids[1], self.getWidth())
        else:
            return o_add(v1, v2.kids[1], self.getWidth())

    return None

def handle_const_on_left(self, v2):
    '''
    if constant is on the left for a subtraction operation, perform a
    replacement so it's on the right since thats how our rules work.
    (255 - foo) => (0 - foo) + 255
    '''
    if (isinstance(v2, o_sub) and
        v2.kids[0].isDiscrete() and
        not v2.kids[1].isDiscrete()):

        v2 = o_add(o_sub(Const(0, self.getWidth()), v2.kids[1], self.getWidth()), v2.kids[0], self.getWidth())

    return v2

def op_reduce_addsub(self, v1, v1val, v2, v2val, emu):

    ret = handle_zero_in_leaf(self, v1, v1val, v2, v2val)
    if ret != None:
        return ret

    ret = handle_zero_in_leaf_from_parent(self, v1, v1val, v2, v2val)
    if ret != None:
        return ret

    # if our op width is the same as the kids widths and the kids are consts
    # or add/sub operations, we may be able to combine some of the terms.
    # if we can't, we can't reduce anything.
    if (self.getWidth() != v1.getWidth() or
        v1.getWidth() != v2.getWidth() or
        not self.isConstOrAddSub(v1) or
        not self.isConstOrAddSub(v2)):
        return None

    # normalize the kids if we have to
    v1 = handle_const_on_left(self, v1)
    v2 = handle_const_on_left(self, v2)

    # given the input ops, lookup what the output ops are
    pclass, k0class, k1class, swapc, swapnc = addsub_table[(self.__class__, v1.__class__, v2.__class__)]

    ckid1, ckid2 = self.getConstKids(v1, v2)

    # combine the const kids into a term
    # some operations cause the kids to position to matter (sub)
    if swapc == True:
        kid1 = k1class(ckid2, ckid1, self.getWidth()).reduce()
    else:
        kid1 = k1class(ckid1, ckid2, self.getWidth()).reduce()

    nckid0, nckid1 = self.getNonConstKids(v1, v2)
    # handle the case where a leaf only has a constant and no non-const kids.
    # (see test_one and test_two in unit tests for examples)
    if nckid0 == None or nckid1 == None:
        nckid = nckid0
        if nckid == None:
            nckid = nckid1

        # combine the non-const term and const term into a term
        if swapnc == True:
            return pclass(kid1, nckid, self.getWidth())
        else:
            return pclass(nckid, kid1, self.getWidth())

    # combine the non-const kids into a term
    nckid = k0class(nckid0, nckid1, self.getWidth())

    # combine the non-const term and const term into a term
    ncop = pclass(nckid, kid1, self.getWidth()).reduce()

    return ncop

class o_add(Operator):
    operstr = '+'
    oper = operator.add

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        return op_reduce_addsub(self, v1, v1val, v2, v2val, emu)

class o_sub(Operator):
    operstr = '-'
    oper = operator.sub

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        return op_reduce_addsub(self, v1, v1val, v2, v2val, emu)

# lookup table for add/sub operations. the table format is:
# key - input classes for parent, kid0, and kid1
# value - output classes for parent, kid0, and kid1
# this was 'generated' by writing each case out and observing the change.
# fex:
#      -                                +
#   -     -    is transformed to:   -       -
# which is in the table as:
# (o_sub, o_sub, o_sub) : (o_add, o_sub, o_sub, True),
#
# this is observable from:
# (v1 - c1) - (v2 - c2) => (v1 - v2) + (c2 - c1)
#
# look at the unit tests and this table at the same time to view more examples.
addsub_table = {
        (o_add, o_add, Const) : (o_add, None, o_add, False, False),
        (o_add, Const, o_add) : (o_add, None, o_add, False, False),

        (o_add, o_sub, Const) : (o_add, None, o_sub, True, False),
        (o_add, Const, o_sub) : (o_add, None, o_sub, False, False),

        (o_sub, o_add, Const) : (o_add, None, o_sub, False, False),
        (o_sub, Const, o_add) : (o_sub, None, o_sub, False, True),

        (o_sub, o_sub, Const) : (o_sub, None, o_add, False, False),
        (o_sub, Const, o_sub) : (o_sub, None, o_add, False, True),

        (o_add, o_add, o_add) : (o_add, o_add, o_add, False, False),
        (o_add, o_sub, o_add) : (o_add, o_add, o_sub, True, False),
        (o_add, o_add, o_sub) : (o_add, o_add, o_sub, False, False),
        (o_add, o_sub, o_sub) : (o_sub, o_sub, o_add, False, False),

        (o_sub, o_add, o_add) : (o_add, o_sub, o_sub, False, False),
        (o_sub, o_sub, o_add) : (o_sub, o_sub, o_add, False, False),
        (o_sub, o_add, o_sub) : (o_add, o_sub, o_add, False, False),
        (o_sub, o_sub, o_sub) : (o_add, o_sub, o_sub, True, False),
        }

class o_xor(Operator):
    operstr = '^'
    oper = operator.xor

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        v1width = v1.getWidth()
        v2width = v2.getWidth()
        if v1val == v2val and v1width == v2width:
            return Const(0, v1width)

        if v1val == 0:
            return v2

        if v2val == 0:
            return v1

class o_and(Operator):
    operstr = '&'
    oper = operator.and_

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        v1width = v1.getWidth()
        v2width = v2.getWidth()

        # collapse nested discrete AND notation
        if isinstance(v1, o_and):
            if v2.isDiscrete():

                if v1.kids[1].isDiscrete():
                    newmask = v1.kids[1].solve() & v2val
                    v1.kids[1] = Const(newmask, v1width)
                    v1._strval = None
                    return v1

                if v1.kids[0].isDiscrete():
                    newmask = v1.kids[0].solve() & v2val
                    v1.kids[0] = Const(newmask, v1width)
                    v1._strval = None
                    return v1

        if isinstance(v2, o_and):

            if v1.isDiscrete():
                if v2.kids[1].isDiscrete():
                    newmask = v2.kids[1].solve() & v1val
                    v2.kids[1] = Const(newmask, v2width)
                    v2._strval = None
                    return v2

                if v2.kids[0].isDiscrete():
                    newmask = v2.kids[0].solve() & v1val
                    v2.kids[0] = Const(newmask, v2width)
                    v2._strval = None
                    return v2

        v1umax = e_bits.u_maxes[v1width]
        v2umax = e_bits.u_maxes[v2width]

        if v2val & v1umax == v1umax and v1width == v2width:
            return v1

        if v1val & v2umax == v2umax and v1width == v2width:
            return v2

        if v1val == 0 and v1width == v2width:
            return Const(0, v1width)

        if v2val == 0 and v1width == v2width:
            return Const(0, v2width)

        if v1val == v2val:
            return v1

class o_or(Operator):
    operstr = '|'
    oper = operator.or_

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        v1width = v1.getWidth()
        v2width = v2.getWidth()
        v1umax = e_bits.u_maxes[v1width]
        v2umax = e_bits.u_maxes[v2width]

        if v1val == v1umax and v1width == v2width:
            return Const(v1umax, v1width)

        if v2val == v2umax and v1width == v2width:
            return Const(v2umax, v2width)

        if v1val == 0:
            return v2

        if v2val == 0:
            return v1

class o_mul(Operator):
    operstr = '*'
    oper = operator.mul

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        v1width = v1.getWidth()
        v2width = v2.getWidth()

        if v1val == 0 and v1width == v2width:
            return Const(0, v1width)

        if v2val == 0 and v1width == v2width:
            return Const(0, v2width)

        if v1val == 1:
            return v2

        if v2val == 1:
            return v1

class o_div(Operator):
    operstr = '/'
    oper = operator.div # should this be floordiv?

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        v1width = v1.getWidth()
        v2width = v2.getWidth()
        if v1val == 0 and v1width == v2width:
            return Const(0, v1width)

class o_mod(Operator):
    operstr = '%'
    oper = operator.mod

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        v1width = v1.getWidth()
        v2width = v2.getWidth()
        if v1val == 0 and v1width == v2width:
            return Const(0, v1width)

class o_lshift(Operator):
    operstr = '<<'
    oper = operator.lshift

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        if v2val == 0:
            return v1

        v1width = v1.getWidth()
        v2width = v2.getWidth()
        if v1val == 0 and v1width == v2width:
            return Const(0, v1width)

class o_rshift(Operator):
    operstr = '>>'
    oper = operator.rshift

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        if v2val == 0:
            return v1

        v1width = v1.getWidth()
        v2width = v2.getWidth()
        if v1val == 0 and v1width == v2width:
            return Const(0, v1width)

class o_pow(Operator):
    operstr = '**'
    oper = operator.pow

    def _op_reduce(self, v1, v1val, v2, v2val, emu):
        # for starters, anything to the 1th is itself...
        if v2val == 1:
            return v1

        v1width = v1.getWidth()
        v2width = v2.getWidth()
        # Anything to the 0th is 1...
        if v2val == 0 and v1width == v2width:
            return Const(1, v2width)

        if v1val == 1:
            return Const(1, v1width)

# introduce the concept of a modifier?  or keep this an operator?
class o_sextend(SymbolikBase):

    def __init__(self, cursz, tgtsz, v1):
        SymbolikBase.__init__(self)
        self.kids   = [v1,]
        self._cursz = cursz
        self._tgtsz = tgtsz

    def __repr__(self):
        return '%s(%s, %s, %s)' % (self.__class__.__name__, repr(self._cursz), repr(self._tgtsz), repr(self.kids[0]))

    def __str__(self):
        if self._strval:
            return self._strval

        operstr = 'signextend( %s, %s, %s )'
        return operstr % (str(self._cursz), str(self._tgtsz), str(self.kids[0]))

    def getWidth(self):
        # TODO: review
        return self.kids[0].getWidth()

    def walkTree(self, cb, ctx=None, walktag=None):

        self.kids[0].walkTree(cb, ctx=ctx, walktag=walktag)      # do we really want to walk the sizes?
        self._cursz.walkTree(cb, ctx=ctx, walktag=walktag)
        self._tgtsz.walkTree(cb, ctx=ctx, walktag=walktag)

        self.kids[0] = cb(self.kids[0], ctx)        # do we really want to call the callback on sizes?
        self._cursz = cb(self._cursz, ctx)
        self._tgtsz = cb(self._tgtsz, ctx)

    def _solve(self, emu=None):
        v1 = self.kids[0].solve(emu=emu)
        cursz = self._cursz.solve(emu=emu)
        tgtsz = self._tgtsz.solve(emu=emu)
        return e_bits.sign_extend( v1, cursz, tgtsz )

    def _reduce(self, emu=None):
        self._strval = ''
        v1 = self.kids[0].reduce(emu=emu)
        v1val = v1.solve(emu=emu)

        cursz = self._cursz.reduce(emu=emu)
        curszval = cursz.solve(emu=emu)

        tgtsz = self._tgtsz.reduce(emu=emu)
        tgtszval = tgtsz.solve(emu=emu)

        # All operators should check for discrete...
        if v1.isDiscrete() and cursz.isDiscrete() and tgtsz.isDiscrete():
            return Const(self.solve(emu=emu), self.kids[0].getWidth())

        ret = self._op_reduce(v1, v1val, cursz, curszval, tgtsz, tgtszval, emu)
        if ret != None:
            return ret

        self.kids[0] = v1
        self._cursz = cursz
        self._tgtsz = tgtsz
        return self

    def update(self, emu):
        v1 = self.kids[0].update(emu)
        cursz = self._cursz.update(emu)
        tgtsz = self._tgtsz.update(emu)
        return self.__class__(cursz, tgtsz, v1)

    def _op_reduce(self, v1, v1val, cursz, curszval, tgtsz, tgtszval, emu=None):
        # Override this to do per operator special reduction
        return None

    def reverse(self):
        return m_shrink(self._tgtsz, self._cursz, self.kids[0])

    def isDiscrete(self, emu=None):
        return self.kids[0].isDiscrete(emu=emu) and self._cursz.isDiscrete(emu=emu) and self._tgtsz.isDiscrete(emu=emu)
