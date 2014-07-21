import vivisect.tools.graphutil as viv_graph
import vivisect.symboliks.effects as vsym_effects
import vivisect.symboliks.emulator as vsym_emulator

from vivisect.const import *
from vivisect.symboliks.common import *

class SymbolikFunctionEmulator(vsym_emulator.SymbolikEmulator):
    '''
    A special symbolik emulator specifically extended for use in
    emulating functions (with things like calling conventions, etc...)
    '''

    def __init__(self, vw):
        vsym_emulator.SymbolikEmulator.__init__(self, vw)
        self.cconvs = {}
        self.cconv = None   # This will be set by setupFunctionCall

        #self.apimod = self.getApiModule()
        self.funchooks = {}

    def setupFunctionCall(self, fva, args=None):
        '''
        Setup the input context for a sequence of symbolik effects which
        represent a function call.  This will initialize the emulator so
        things like [esp + 8] have an existing state which is "arg0" or even a
        value (based on input args...)
        '''
        # Setup our calling convention based on what the workspace says
        # for this function...
        apictx = self._sym_vw.getFunctionApi(fva)
        if apictx == None:
            raise Exception('No API context for function %x' % fva)
        
        ccname = apictx[API_CCONV]
        self.cconv = self.getCallingConvention(ccname)
        if self.cconv == None:
            raise Exception('Unknown CallingConvention (%s) for: 0x%.8x' % (ccname,fva))

        # Initialize arguments by setting variables based on their names...
        funcargs = self._sym_vw.getFunctionArgs(fva)

        if args == None:
            args = [ Var(aname, len(atype)) for atype, aname in funcargs ]

        if len(args) != len(funcargs):
            raise Exception('Invalid Symbolik Args (%d args given, %d expected)' % (len(args),len(funcargs)))

        self.cconv.setSymbolikArgs(self, args)

    def getFunctionReturn(self):
        '''
        Once the symbolik code for a function has been run through the
        SymbolikFunctionEmulator the getFunctionReturns method will use the
        calling convention object to return the "return" state for this
        function...
        '''
        return self.cconv.getSymbolikReturn(self)

    def applyFunctionCall(self, funcsym):
        '''
        Apply a function call to the current emulation state (where possible,
        emulating as much as possible to update the state to match reality...)

        We return the set of parsed argument syms so the FofX effect updater
        knows...
        '''
        vw = self._sym_vw

        argv = None
        fret = None
        cconv = None
        symargs = ()

        # If this is a discrete function, use knowledge from the workspace to
        # attempt to properly cleanup the call (and setup a state)
        if funcsym.isDiscrete():

            fva = funcsym.solve(emu=self)

            # since it's discrete, call the solver and resolve fva
            if self._sym_vw.isFunction(fva):

                # If viv knows about this function, lets check if it's a thunk,
                # or if we know about it's calling info...
                fname = vw.getName(fva)
                argv = vw.getFunctionArgs(fva)
                thunk = vw.getFunctionMeta(fva, 'Thunk')

                apictx = self._sym_vw.getFunctionApi(fva)
                if apictx == None:
                    raise Exception('No API context for function %x' % fva)
                ccname = apictx[API_CCONV]

                cconv = self.getCallingConvention(ccname)
                # Either way, if we have a calling convention and a function def
                # lets parse out our arguments so the FofX() effect can have
                # more info
                if cconv != None:
                    symargs = cconv.getSymbolikArgs(self, argv, update=True)

                # First of all, if the name of the function has a callback
                funccb = self.getFunctionCallback(fname)
                if funccb != None:
                    fret = funccb(self, fname, symargs)

                # Next highest priority is "thunks" where there is a callback
                elif thunk != None:
                    funccb = self.getFunctionCallback(thunk)
                    if funccb != None:
                        fret = funccb(self, thunk, symargs)

        else:

            funcname = str(funcsym)     # Not necessarily the name but...

            # Attempt to use import api definitions...
            apidef = self._sym_vw.getImpApi( funcname )
            if apidef:
                #( 'int', None, 'stdcall', 'wininet.FindFirstUrlCacheContainerW', (('int', None), ('void *', 'ptr'), ('int', None), ('int', None)) ),
                rt,rn,cc,fn,argv = apidef
                cconv = self.getCallingConvention( cc )

            # If we managed to get a calling convention *and* argument def...
            if cconv != None and argv != None:
                symargs = cconv.getSymbolikArgs(self, argv, update=True)

            # Give the function callback a shot...
            funccb = self.getFunctionCallback(funcname)
            if funccb != None:
                fret = funccb(self, funcname, symargs)

        # If we have a calling convention here, set the return state
        if cconv != None:
            if fret == None:
                # TODO: yuck. take ez way out and use width on emu.
                # should get return value def from cc and set width according
                # to width of that?
                fret = Call(funcsym, self.__width__, symargs)
            cconv.setSymbolikReturn(self, fret, argv)

        return symargs

    def addCallingConvention(self, name, symcconv):
        '''
        Add a *symbolik* calling convention object to this analysis context.
        The context will be used for operations like argument initialization
        and return value extraction for symbolik emulation.

        (add a calling convention with the name None (object, not string) to
        specify a "default" calling convention)
        '''
        self.cconvs[name] = symcconv

    def getCallingConvention(self, name, default=None):
        '''
        Retrieve a registered *symbolik* calling convention object by name.
        '''
        return self.cconvs.get(name, default)

    def getCallingConventions(self):
        '''
        Retrieve a list of (name, ccobj) tuples for the registered *symbolik*
        calling convention objects in this context.
        '''
        return self.cconvs.items()

    def addFunctionCallback(self, funcname, callback):
        '''
        Function hooks may be registered which will get an opportunity to modify
        the emulator state during *runtime* upon the detection of a call to a
        function with the same name (or an import/thunk of the same name...)

        NOTE: a function callback is expected to *completely* handle updating
        the state of the emulator for the function call.
        '''
        self.funchooks[funcname] = callback

    def getFunctionCallback(self, funcname):
        '''
        Retrieve the registered function callback for the given function by name
        (or None if there is no handler registered).
        '''
        return self.funchooks.get(funcname)

    def delFunctionCallback(self, funcname):
        '''
        Remove a registered function callback from the symbolik function
        emulator instance.
        '''
        return self.funchooks.pop(funcname, None)

    ##### Methods to be implemented by arch specific extenders.... ##################

    #def getApiModule(self):
        #'''
        #Architecture extenders may implement this to return an API
        #module which knows about import calling types.
        #'''
        #return None

    def isLocalMemory(self, symaddr, solvedval=None):
        '''
        Because of the assumption of a function calling convention, it is
        possible to determine if a given memory address should be considered a
        "local" memory access based on the given convention...
        '''
        # NOTE: We could make this fall back on self.cconv...
        raise Exception('%s *must* implement isLocalMemory()!' % (self.__class__.__name__))

    def getLocalOffset(self, symaddr, solvedval=None):
        '''
        Return the offset from the initial esp.
        '''
        raise Exception('%s *must* implement getLocalOffset()!' % (self.__class__.__name__))

class SymbolikAnalysisContext:
    '''
    A symbolik analysis context holds arch/platform specific functionality
    which is needed during symboliks analysis...  It is also a context which
    allows over-rides for things like symbolik imports during runtime.
    '''

    def __init__(self, vw):
        self.vw = vw
        self.funccb = {}    # Callbacks
        self.consolve = False

    def getSymbolikGraph(self, fva, fgraph=None):
        '''
        Instantiate a standard vivisect function graph (visgraph
        hierarchical graph) and translate all the opcodes in each block
        to un-applied symbolik effects.  The list of effects for each node
        is stored in 'symbolik_effects' list in the node properties.
        '''
        xlate = self.getTranslator()

        if fgraph == None:
            fgraph = viv_graph.buildFunctionGraph(self.vw, fva)

        for nodeva,ninfo in fgraph.getNodes():

            cbva = ninfo.get('cbva')
            cbsize = ninfo.get('cbsize')

            cbmax = cbva + cbsize
            oplist = []
            while cbva < cbmax:
                op = self.vw.parseOpcode(cbva)
                oplist.append(op)
                cbva += len(op)

            for op in oplist:
                xlate.translateOpcode(op)

            efflist = xlate.getEffects() # we needn't copy
            conlist = xlate.getConstraints()
            xlate.clearEffects()
            # Put constraints into a dictionary lookup by target address
            con_lookup = {}
            for coneff in conlist:
                addrva = coneff.addrsym.solve()
                clist = con_lookup.get(addrva)
                if clist == None:
                    clist = []
                    con_lookup[addrva] = clist
                clist.append(coneff)

            # Save these off in node info for later
            ninfo['opcodes'] = oplist
            ninfo['symbolik_effects'] = efflist

            # Add the constraints to the edges
            for eid,fromid,toid,einfo in fgraph.getRefsFrom(nodeva):
                clist = con_lookup.pop(toid, None)
                if clist == None:
                    continue
                einfo['symbolik_constraints'] = clist

            #if len(con_lookup):
                #raise Exception('FIXME: We ditched a constraint! %s' % repr(con_lookup))

        return fgraph

    def _oposet_cons(self, c1, c2):

        c1v1 = c1._v1.solve()
        c1v2 = c1._v2.solve()

        c2v1 = c2._v1.solve()
        c2v2 = c2._v2.solve()

        if c1v1 == c2v1 and c1v2 == c2v2 and c1.revclass == c2.__class__:
            return True

        if c1v1 == c2v2 and c1v2 == c2v1 and c1.__class__ == c2.__class__:
            return True

        return False

    def _isSat(self, oldcons, newcons):
        # Just detect *super* obvious constraint failures for now...
        if newcons.isDiscrete() and not newcons.prove():
            return False

        for con in newcons:
            if [ c1 for c1 in newcons if self._oposet_cons( c1, con ) ]:
                return False
            if [ c1 for c1 in oldcons if self._oposet_cons( c1, con ) ]:
                return False
        return True

    def addSymFuncCallback(self, name, callback):
        '''
        Register a function callback ( mostly for imports ) in the
        analysis context.  Each function callback will be called when
        an import with the specified name is requested.
        '''
        self.funccb[name] = callback


    def getSymbolikPaths(self, fva, paths=None, args=None, maxpath=1000):
        '''
        For each path through the function, run all symbolik
        effects in an emulator instance and yield
        emu, effects tuples...
        '''
        graph = self.getSymbolikGraph(fva)

        if args == None:
            argdef = self.vw.getFunctionArgs( fva )
            args = [ Arg(i, width=self.vw.psize) for i in xrange(len(argdef)) ]

        if paths == None:
            paths = viv_graph.getCodePaths(graph, maxpath=maxpath)

        #fva = graph.getMeta('fva')  # put in place by buildFunctionGraph...
        pcnt = 0
        for path in paths:
            if pcnt > maxpath:
                break

            pcnt+=1
            skippath = False
            emu = self.getFuncEmu(fva, fargs=args)

            for fname, funccb in self.funccb.items():
                emu.addFunctionCallback(fname, funccb)

            opcodes = []
            patheffects = []
            pathconstraints = []

            for node, edge in path:
                # This is the edge that *got us here* so it has to
                # be processed first!
                if edge != None:
                    constraints = graph.getEdgeInfo(edge, 'symbolik_constraints', ())
                    constraints = emu.applyEffects(constraints)
                    #[ c.reduce() for c in constraints ]

                    #print 'EDGE GOT CONSTRAINTS',[ str(c) for c in constraints]
                    # FIXME check if constraints are discrete, and possibly skip path!
                
                    cons = [ c.cons for c in constraints ]
                    if self.consolve:
                        # If any of the constraints are discrete and false we skip the path
                        discs = [ c.cons.prove() for c in constraints if c.cons.isDiscrete() ]
                        if not all( discs ): # emtpy discs is True...
                            #print('SKIP: %s %s' % (repr(discs),[str(c) for c in constraints ]))
                            skippath = True
                            break

                        #if not self._isSat( pathconstraints , cons):
                            #print('NON SAT: 0x%.8x %s %s' % (node, [ str(c) for c in pathconstraints ], [ str(c) for c in cons ] ))
                            #skippath = True
                            #break

                    patheffects.extend(constraints)
                    pathconstraints.extend( cons )

                if skippath:
                    break

                effects = graph.getNodeInfo(node, 'symbolik_effects', ())
                effects = emu.applyEffects(effects)
                patheffects.extend(effects)

                opcodes.extend( graph.getNodeInfo( node, 'opcodes' ) )

            if not skippath:
                # Store off some info into emu meta for analysis to use
                emu.setMeta('opcodes', opcodes)
                yield emu, patheffects

    def getSymbolikOutputs(self, fva, args=None):
        '''
        For each path in the specified function, run the path with the given
        args (or populate by arg names from workspace).

        Outputs should include:
            globals written to
            input pointers written to
            functions called (with args)
            output registers modified
        '''
        if args == None:
            argdef = self.vw.getFunctionArgs( fva )
            args = [ Arg(i, width=self.vw.psize) for i in xrange(len(argdef)) ]

        for emu, effects in self.getSymbolikPaths(fva, args=args):

            outputeffects = []

            self.vw.vprint('='*80)
            for effect in effects:

                # FIXME calls are probably "outputs" too? (especially import calls...)
                if effect.efftype == vsym_effects.EFFTYPE_WRITEMEM:
                    if not emu.isLocalMemory(effect.symaddr):
                        effect.symaddr.reduce()
                        effect.symval.reduce()
                        outputeffects.append(effect)
                        self.vw.vprint('    WRITE: %s' % str(effect))

            ret = emu.getFunctionReturn()
            ret.reduce()
            self.vw.vprint('RETURN VALUE %s' % ret)
            self.vw.vprint('='*80)

            yield ret, outputeffects 

    def getTranslator(self):
        '''
        Return a symbolik translator for the workspace specified in the
        constructor.
        '''
        return self.__xlator__(self.vw)

    def getFuncEmu(self, fva, fargs=None, args=()):
        '''
        Instantiates a symbolik emulator and if fva is not None, initializes
        the emu for the specified fva.
        Arguments will be populated either by name (from the workspace's
        function definition) or from the argument list specified in args.
        (arguments will be symbolikified if they are strings/ints with a width
        equal to what is specified in the symbolic function emulator)

        Example:
            femu = symctx.getFunctionEmulator(fva, ['arg0', 'arg1', 20])
            femu = symctx.getFuncEmu(None)
        '''
        emu = self.__emu__(self.vw, *args)
        if fva != None:
            fargs = [ frobSymbol(arg, emu.__width__) for arg in fargs ]
            emu.setupFunctionCall(fva, args=fargs)
        return emu

def getSymbolikAnalysisContext(vw):
    '''
    Return a symbolik analysis context which is appropriate for the given
    VivWorkspace.  Returns None if the given arch/platform does not support
    symboliks based analysis yet...
    '''

    arch = vw.getMeta('Architecture')
    if arch == 'i386':
        import vivisect.symboliks.archs.i386 as vsym_i386
        return vsym_i386.i386SymbolikAnalysisContext(vw)

    elif arch == 'amd64':
        import vivisect.symboliks.archs.amd64 as vsym_amd64
        return vsym_amd64.Amd64SymbolikAnalysisContext(vw)

    return None

