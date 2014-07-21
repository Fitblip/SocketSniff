'''
'''
import inspect

import vstruct
import vivisect.symboliks

from vivisect.symboliks.common import *

class CallingConventionProxy:

    def __init__(self, cconv, argv, funcsym):
        self.argv = argv # viv style (type,name) tuple list
        self.cconv = cconv
        self.funcsym = funcsym

    def __call__(self, emu):

        # Get and update the symbolik args
        args = self.cconv.getSymbolikArgs(emu, self.argv)
        args = [ arg.update(emu) for arg in args ]

        # If callFunction returns something, snap it back in.
        # Otherwise, snap in a Call symbol.
        ret = self.callFunction(emu, *args)
        if ret == None:
            # TODO: yuck. take ez way out and use width on emu.
            # should get return value def from cc and set width according
            # to width of that?
            ret = Call(self.funcsym, emu.__width__, args)
        else:
            ret = frobSymbol(ret, emu.__width__)

        # Set the return value into the symbolik state
        self.cconv.setSymbolikReturn(emu, ret, self.argv)

    def getSymbolikArgs(self, emu):
        return self.cconv.getSymbolikArgs(emu, self.argv)

    def callFunction(emu, *args):
        # Each calling convention proxy must implement this to do
        # the actual call hook...
        return None

class ImportCallProxy(CallingConventionProxy):
    '''
    A calling convention proxy allows the definition of
    a pythonic function which may then be called by an emulator
    during symbolik effect processing.
    '''

    def __init__(self, func, cconv):

        # Do crazy introspection shit to make calling convention
        # map function args to names / vstruct types.
        aspec = inspect.getargspec(func)
        argn = aspec.args[1:]
        argt = aspec.defaults

        argv = [ (argt[i],argn[i]) for i in xrange(len(argn)) ]

        modlast = func.__module__.split('.')[-1]
        funcsym = Var('%s.%s' % (modlast, func.__name__))

        CallingConventionProxy.__init__(self, cconv, argv, funcsym)

        self.func = func

    def callFunction(self, emu, *args):
        return self.func(emu, *args)

# FIXME 
'''
def getSymbolikFunction(emu, funcsym):

    archname = emu._sym_vw.getMeta('Architecture')

    # If it has an actual address, see if the workspace knows about it.
    if funcsym.isDiscrete(emu):

        fva = funcsym.solve(emu)

        if emu._sym_vw.isFunction(fva):

            # Check for an import thunk
            thunk = emu._sym_vw.getFunctionMeta(fva, 'Thunk', None)
            if thunk != None and emu._sym_vw.symimpmod != None:
                impfunc = vstruct.resolvepath(emu._sym_vw.symimpmod, thunk)
                if impfunc != None:
                    # Import emulation functions will already be calling convention wrapped
                    return impfunc

            argv = emu._sym_vw.getFunctionArgs(fva)
            apictx = self._sym_vw.getFunctionApi(fva)
            if apictx == None:
                raise Exception('No API context for function %x' % fva)
            ccname = apictx[API_CCONV]

        else:
            # If it's discrete, and the workspace doesn't know about it,
            # punt...  we *could* consider making it a function...
            argv = ()
            ccname = 'default'

        cconv = vstruct.resolve(vivisect.symboliks, (archname, ccname))

        return CallingConventionProxy(cconv, argv, funcsym)


    # Lets see if the symstr jive's with an import name
    symstr = str(funcsym)
    if emu._sym_vw.symimpmod != None:
        impfunc = vstruct.resolvepath(emu._sym_vw.symimpmod, symstr)
        if impfunc != None:
            # Import emulation functions will already be calling convention wrapped
            return impfunc

    cconv = vstruct.resolve(vivisect.symboliks, (archname,'default'))
    return CallingConventionProxy(cconv, (), funcsym)


'''
