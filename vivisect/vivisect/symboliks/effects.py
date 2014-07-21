import vivisect.symboliks.functions as vsym_funcs

from vivisect.symboliks.common import *
from vivisect.symboliks.constraints import *

EFFTYPE_DEBUG        = 0
EFFTYPE_SETVAR       = 1
EFFTYPE_READMEM      = 2
EFFTYPE_WRITEMEM     = 3
EFFTYPE_CALLFUNC     = 4
EFFTYPE_CONSTRAIN    = 5

class SymbolikEffect:
    '''
    A single symbolik effect...
    '''
    efftype = None

    def __init__(self, va):
        self.va = va

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        raise Exception('%s must implement __eq__!' % (self.__class__.__name__,))

    def reduce(self, emu=None):
        raise Exception('%s must implement reduce()!' % (self.__class__.__name__))

    def walkTree(self, cb, ctx=None, walktag=None):
        raise Exception('%s must implement walkTree()!' % (self.__class__.__name__))

    def applyEffect(self, emu):
        raise Exception('%s must implement applyEffect!' % (self.__class__.__name__,))

class DebugEffect(SymbolikEffect):
    '''
    DebugEffect is used to represent an NOP effect that we want logged.
    Example: DebugEffect is created for instructions that are unsupported.

        return DebugEffect(op.va, "%s Needs %s" % (self.__class__.__name__, repr(op)))
    '''
    efftype = EFFTYPE_DEBUG

    def __init__(self, va, msg):
        SymbolikEffect.__init__(self, va)
        self.msg = msg

    def __repr__(self):
        return 'DebugEffect(0x%.8x, %s)' % (self.va, self.msg) 

    def __str__(self):
        return '%s' % self.msg 

    def __eq__(self, other):
        if other == None:
            return False
        if self.__class__ != other.__class__:
            return False
        if not self.msg == other.msg:
            return False

        return True

    def walkTree(self, cb, ctx=None, walktag=None):
        pass

    def reduce(self, emu=None):
        pass

    def applyEffect(self, emu):
        return self

class SetVariable(SymbolikEffect):

    efftype = EFFTYPE_SETVAR

    def __init__(self, va, varname, symobj):
        SymbolikEffect.__init__(self, va)
        self.varname = varname
        self.symobj = symobj

    def __repr__(self):
        return 'SetVariable(0x%.8x, %s, %s)' % (self.va, repr(self.varname), repr(self.symobj))

    def __str__(self):
        return '%s = %s' % (self.varname, str(self.symobj))

    def __eq__(self, other):
        if other == None:
            return False
        if self.__class__ != other.__class__:
            return False
        if not self.varname == other.varname:
            return False
        if not self.symobj == other.symobj:
            return False

        return True

    def walkTree(self, cb, ctx=None, walktag=None):
        self.symobj.walkTree(cb, ctx=ctx, walktag=walktag)
        self.symobj = cb(self.symobj, ctx)

    def reduce(self, emu=None):
        self.symobj = self.symobj.reduce(emu=emu)

    def applyEffect(self, emu):
        symobj = self.symobj.update(emu)
        emu.setSymVariable(self.varname, symobj)
        return SetVariable(self.va, self.varname, symobj)

class ReadMemory(SymbolikEffect):

    efftype = EFFTYPE_READMEM

    def __init__(self, va, symaddr, symsize):
        SymbolikEffect.__init__(self, va)
        self.symaddr = symaddr
        self.symsize = symsize

    def __repr__(self):
        t = (self.va, repr(self.symaddr), repr(self.symsize))
        return 'ReadMemory( 0x%.8x, %s, %s )' % t

    def __str__(self):
        return '[ %s : %s ]' % (str(self.symaddr), str(self.symsize))

    def __eq__(self, other):
        if other == None:
            return False
        if self.__class__ != other.__class__:
            return False
        if not self.symaddr == other.symaddr:
            return False
        if not self.symsize == other.symsize:
            return False

        return True

    def walkTree(self, cb, ctx=None, walktag=None):
        self.symaddr.walkTree(cb, ctx=ctx, walktag=walktag)
        self.symsize.walkTree(cb, ctx=ctx, walktag=walktag)
        self.symaddr = cb(self.symaddr, ctx)
        self.symsize = cb(self.symsize, ctx)

    def reduce(self, emu=None):
        self.symaddr = self.symaddr.reduce(emu=emu)
        self.symsize = self.symsize.reduce(emu=emu)

    def applyEffect(self, emu):
        symaddr = self.symaddr.update(emu)
        symsize = self.symsize.update(emu)
        return ReadMemory(self.va, symaddr, symsize)

class WriteMemory(SymbolikEffect):

    efftype = EFFTYPE_WRITEMEM

    def __init__(self, va, symaddr, symsize, symval):
        SymbolikEffect.__init__(self, va)
        self.symval = symval
        self.symaddr = symaddr
        self.symsize = symsize

    def __repr__(self):
        t = (self.va, repr(self.symaddr), repr(self.symsize), repr(self.symval))
        return 'WriteMemory( 0x%.8x, %s, %s, %s)' % t

    def __str__(self):
        t = (str(self.symaddr), str(self.symsize), str(self.symval))
        return '[ %s : %s ] = %s' % t

    def __eq__(self, other):
        if other == None:
            return False
        if self.__class__ != other.__class__:
            return False
        if not self.symval == other.symval:
            return False
        if not self.symaddr == other.symaddr:
            return False
        if not self.symsize == other.symsize:
            return False

        return True

    def walkTree(self, cb, ctx=None, walktag=None):
        self.symval.walkTree(cb, ctx=ctx, walktag=walktag)
        self.symaddr.walkTree(cb, ctx=ctx, walktag=walktag)
        self.symsize.walkTree(cb, ctx=ctx, walktag=walktag)

        self.symval = cb(self.symval, ctx)
        self.symaddr = cb(self.symaddr, ctx)
        self.symsize = cb(self.symsize, ctx)

    def reduce(self, emu=None):
        self.symaddr = self.symaddr.reduce(emu=emu)
        self.symsize = self.symsize.reduce(emu=emu)
        self.symval  = self.symval.reduce(emu=emu)

    def applyEffect(self, emu):
        symaddr = self.symaddr.update(emu)
        symsize = self.symsize.update(emu)
        symval = self.symval.update(emu)
        emu.writeSymMemory(symaddr, symval)
        return WriteMemory(self.va, symaddr, symsize, symval)

class CallFunction(SymbolikEffect):
    '''
    This effect represents a procedural branch.  They are recorded specially
    because they may have effect on the overall system even though their
    outputs are not stored.

    NOTE: argsyms will be None while we haven't had a definition to use..
    '''

    efftype = EFFTYPE_CALLFUNC

    def __init__(self, va, funcsym, argsyms=None):
        SymbolikEffect.__init__(self, va)
        self.funcsym = funcsym
        self.argsyms = argsyms

    def __repr__(self):
        return 'CallFunction( 0x%.8x, %s, %s )' % (self.va, repr(self.funcsym), repr(self.argsyms))

    def __str__(self):
        argstr = '?'
        if self.argsyms != None:
            argstr = ','.join( str(x) for x in self.argsyms )
        return '%s(%s)' % (self.funcsym, argstr)

    def __eq__(self, other):
        if other == None:
            return False
        if self.__class__ != other.__class__:
            return False
        if not self.funcsym == other.funcsym:
            return False
        if not self.argsyms == other.argsyms:
            return False

        return True

    def walkTree(self, cb, ctx=None, walktag=None):
        self.funcsym.walkTree(cb, ctx=ctx, walktag=walktag)
        x = [ arg.walkTree(cb, ctx=ctx, walktag=walktag) for arg in self.argsyms ]

        self.funcsym = cb(self.funcsym, ctx)
        self.argsyms = [ cb(arg, ctx) for arg in self.argsyms ]

    def reduce(self, emu=None):
        self.funcsym = self.funcsym.reduce(emu=emu)
        if self.argsyms != None:
            self.argsyms = [ x.reduce(emu=emu) for x in self.argsyms ]

    def applyEffect(self, emu):
        funcsym = self.funcsym.update(emu)

        # If we have argsyms, the function's work has been broken out
        # already (probably by applying effects once already...)
        if self.argsyms != None:
            argsyms = [ x.update(emu) for x in self.argsyms ]
            return CallFunction(self.va, funcsym, argsyms)

        # Without argsyms, we are probably a call who is being applied to
        # an emulator for the first time!  Let the emulator handle it...
        argsyms = emu.applyFunctionCall(funcsym)
        return CallFunction(self.va, funcsym, argsyms)

class ConstrainPath(SymbolikEffect):

    efftype = EFFTYPE_CONSTRAIN

    def __init__(self, va, addrsym, cons):
        SymbolikEffect.__init__(self, va)
        self.addrsym = addrsym
        self.cons = cons

    def walkTree(self, cb, ctx=None, walktag=None):
        self.cons.walkTree(cb, ctx=ctx, walktag=walktag)
        self.cons = cb(self.cons, ctx)

    def reduce(self, emu=None):
        self.addrsym = self.addrsym.reduce(emu=emu)
        self.cons = self.cons.reduce(emu=emu)

    def __repr__(self):
        return 'ConstrainPath( 0x%.8x, %s, %s )' % (self.va, repr(self.addrsym), repr(self.cons))

    def __str__(self):
        return 'if (%s)' % (str(self.cons),)

    def __eq__(self, other):
        if other == None:
            return False
        if self.__class__ != other.__class__:
            return False
        if not self.addrsym == other.addrsym:
            return False
        if not self.cons == other.cons:
            return False

        return True

    def applyEffect(self, emu):
        addrsym = self.addrsym.update(emu)
        cons = self.cons.update(emu)
        return ConstrainPath(self.va, addrsym, cons)

