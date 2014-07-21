
import hashlib
import vivisect
import vivisect.cli as viv_cli

import vivisect.tools.graphutil as viv_graphutil

'''
TODO:  Bolster likely matches (not perfect matches) with *function* graph
       data showing their parent/children *function* signatures.

NOTES: Could we use branch mnemonic as node "type"?
       Could we use block-mnemonic-list as type?
       Could we use references to non-pointer immediates as identifiers?
       Could we use use references to strings as anchors?
       Could we use symboliks reduction here?  I bet so... ;)
'''

def getOtherWorkspace(wsname):
    vw = viv_cli.VivCli()
    vw.loadWorkspace(name)
    return vw

def getBlockMnems(vw, bva, bsize):
    ret = []
    bend = bva + bsize
    while bva < bend:
        op = vw.parseOpcode(bva)
        ret.append(op.mnem)
        bva += len(op)
    return ''.join(ret)

FHASH_MNEM      = 1
FHAHS_GRAPH     = 2

class CodeDiff:

    '''
    The CodeDiff class is a context for diffing multiple vivisect
    workspaces to identify shared or changed code.  Most of the purpose
    for this object is to maintain a diff configuration context to allow
    twiddling the engine heuristic behavior...
    '''

    def __init__(self, vw1, vw2):
        self.vw1 = vw1
        self.vw2 = vw2

        # Options for function hashing
        self.fhash_type = FHASH_MNEM

        # These will be dictionaries populated with
        # <fsig>: ( fva, fname) tuples
        self._v1_fsigs = None
        self._v2_fsigs = None

    def _functionDiff(self):
        # Actually generate the diff data for functions
        self._v1_fsigs = self.getFunctionDiffHashes(self.vw1)
        self._v2_fsigs = self.getFunctionDiffHashes(self.vw2)

    def getFunctionDiffHashes(self, vw):

        fsigret = {}
        for fva in vw.getFunctions():
            try:
                fsig = self.getFunctionHash(vw, fva)
                fsigret[fsig] = ( fva, vw.getName(fva) )
            except Exception, e:
                import traceback
                traceback.print_exc()
                print 'ERROR: %s' % str(e)

        return fsigret

    def getBlockDifferences(self, fva1, fva2):
        '''
        For an already strong(ish) matching function, check which blocks
        are present and return a list of the differences.
        '''
        f1blocks = self.vw1.getFunctionBlocks(fva1)
        f1hashes = {}
        f1mnems = []
        for cbva, cbsize, fva in f1blocks:
            mnem = getBlockMnems(self.vw1, cbva, cbsize)
            f1hashes[mnem] = (cbva, cbsize, fva)
            f1mnems.append(mnem)

        s1 = set(f1mnems)

        f2blocks = self.vw2.getFunctionBlocks(fva2)
        f2hashes = {}
        f2mnems = []
        for cbva, cbsize, fva in f2blocks:
            mnem = getBlockMnems(self.vw2, cbva, cbsize)
            f2hashes[mnem] = (cbva, cbsize, fva)
            f2mnems.append(mnem)

        s2 = set(f2mnems)

        res1 = s1 - s2
        res2 = s2 - s1

        ret1 = [ f1hashes.get(m) for m in res1 ]
        ret2 = [ f2hashes.get(m) for m in res2 ]

        return ret1, ret2

    def getFunctionHash(self, vw, fva):

        rowpos = {}

        g = viv_graphutil.buildFunctionGraph(vw, fva)
        weights = g.getNodeWeights()

        #print '0x%.8x: %d' % (fva, len(g.getNodes()))

        # Here, we assume that the calculation of "node order" is consistant
        # because it is dependant on the graphutil code following branches in
        # a consistant way.

        # NOTE: This is a good way to identify totally identical functions, but
        # a terrible way to tell *what* changed due to all subsequant nodes being
        # bumped and moved around...

        for nid,ninfo in g.getNodes():
            # Set each node's "node identifier" info
            # ( which is currently, nodeid:depth:rowpos
            weight = weights.get(nid, -1)
            row = rowpos.get(weight)
            if row == None:
                row = []
                rowpos[weight] = row

            # Just ID information and graph layout... (may allow matching
            # even in the presence of compiler optimization
            #ninfo['diff_node'] = '%d:%d:%d' % (nid, weight, len(row))

            # Mnemonics and graph layouts.  Probably the most twitchy match...
            #mnems = getBlockMnems(vw, ninfo['cbva'], ninfo['cbsize'])
            #ninfo['diff_node'] = '%s:%d:%d' % (mnems, weight, len(row))

            # FIXME this could also do hash's of above/below to do block compare...

            # Just the mnemonics... (may allow block comparison *inside* funcions with diffs)
            mnems = getBlockMnems(vw, ninfo['cbva'], ninfo['cbsize'])
            ninfo['diff_node'] = mnems

            #print nid,ninfo['diff_node']
            row.append(nid)


        # The *actual* data we use to unique the function is the *relationship*
        # between nodes rather than the nodes themselves.  Each node's 'diff_node'
        # identifier is assumed to be non-unique, but grouping.  The relationship
        # between nodes is used to feed a sha1 hash...
        edgediff = []
        for eid, fromid, toid, einfo in g.getEdges():
            fromdiff = g.getNodeInfo(fromid, 'diff_node')
            todiff   = g.getNodeInfo(toid, 'diff_node')
            edgediff.append('%s|%s' % (fromdiff, todiff))

        edgediff.sort()

        return hashlib.sha1(','.join(edgediff)).hexdigest()

    def getFunctionDeltas(self):
        '''
        Return a tuple of ( <vw1_unique>, <vw2_unique>, <common>)
        function lists.
        '''
        h1 = self.getFunctionDiffHashes(self.vw1)
        h2 = self.getFunctionDiffHashes(self.vw2)

        vw1_unique = []
        vw2_unique = []
        common = []

        for k,v in h1.items():
            k2 = h2.get(k)
            if k2 == None:
                vw1_unique.append(v)
            else:
                common.append((v, k2))

        for k,v in h2.items():
            k1 = h1.get(k)
            if k1 == None:
                vw2_unique.append(v)

        return vw1_unique, vw2_unique, common


def getFunctionEdgeList(vw, fva):
    '''
    Return a list of b1mnems|b2mnems strings where b*mnems is a list
    of the instruction mnemonics for each block.  This creates a list of
    "edges" rather than a list of blocks which makes false positive matches
    on similar blocks less likely.
    '''

    g = viv_graphutil.buildFunctionGraph(vw, fva)

    # A variant on the function hash graph stuff which allows
    # similarity comparison...

    for nid,ninfo in g.getNodes():

        # Just the mnemonics... (may allow block comparison *inside* funcions with diffs)
        mnems = getBlockMnems(vw, ninfo['cbva'], ninfo['cbsize'])
        ninfo['diff_node'] = mnems

    # Similar to get function hash but the data in the block relationship *must*
    # be more stable across changes to identify the totally new blocks
    edgediff = []
    for eid, fromid, toid, einfo in g.getEdges():
        fromdiff = g.getNodeInfo(fromid, 'diff_node')
        todiff   = g.getNodeInfo(toid, 'diff_node')
        edgediff.append('%s|%s' % (fromdiff, todiff))

    return edgediff

def getFunctionDeltas(vw1, vw2):
    '''
    Return a tuple of ( <vw1_unique>, <vw2_unique>, <common>)
    function lists.
    '''

#def printCodeDeltas(vw1, vw2):

#vw1 = vivisect.VivWorkspace()
#vw1.loadWorkspace(sys.argv[1])

#vw2 = vivisect.VivWorkspace()
#vw2.loadWorkspace(sys.argv[2])

    # FIXME assuming the first one has the console...

    diff = CodeDiff(vw1, vw2)

    h1 = diff.getFunctionDiffHashes(vw1)
    h2 = diff.getFunctionDiffHashes(vw2)

    vw1_unique = []
    vw2_unique = []
    common = []

    for k,v in h1.items():
        k2 = h2.get(k)
        if k2 == None:
            vw1_unique.append(v)
        else:
            common.append((v, k2))

    for k,v in h2.items():
        k1 = h1.get(k)
        if k1 == None:
            vw2_unique.append(v)

    return vw1_unique, vw2_unique, common

def getBestBlockMatch(edgelist, f2einfo):
    '''
    For the specified edge list, go through the functions the
    supplied f2einfo dictionary and find the one with the most
    in common...
    '''
    # FIXME could all blocks in one hash make it better?
    mscorebest = 0
    mbestva = 0
    for f2va in f2einfo.keys():
        f2edgelist = f2einfo.get(f2va)
        matchlist = [ x for x in edgelist if x in f2edgelist ]
        mscore = len(matchlist) / float(len(edgelist))
        if mscore > mscorebest:
            mscorebest = mscore
            mbestva = f2va
    return (mbestva, mscorebest)

def printCodeDeltas(vw1, vw2):

    vw1_u, vw2_u, vw_common = getFunctionDeltas(vw1, vw2)

    v1binfo = {}
    for fva, fname in vw1_u:
        v1binfo[fva] = getFunctionEdgeList(vw1, fva)

    v2binfo = {}
    for fva, fname in vw2_u:
        v2binfo[fva] = getFunctionEdgeList(vw2, fva)

    v1_soft_matches = {}
    for fva, fname in vw1_u:
        edgelist = v1binfo.get(fva)
        v1_soft_matches[fva] = getBestBlockMatch(edgelist, v2binfo)

    v2_soft_matches = {}
    for fva, fname in vw2_u:
        edgelist = v2binfo.get(fva)
        v2_soft_matches[fva] = getBestBlockMatch(edgelist, v1binfo)

    vw1.vprint('%s Unique =====' % vw1.getMeta('StorageName'))
    for fva, fname in vw1_u:
        softstr = ''
        bestva, bestscore = v1_soft_matches.get(fva)
        vw1.vprint('0x%.8x %s bestmatch 0x%.8x %d%%' % (fva, fname, bestva, bestscore * 100))

    vw1.vprint('%s Unique =====' % vw2.getMeta('StorageName'))
    for fva, fname in vw2_u:
        bestva, bestscore = v2_soft_matches.get(fva)
        vw1.vprint('0x%.8x %s bestmatch 0x%.8x %d%%' % (fva, fname, bestva, bestscore * 100))

    for v1,v2 in vw_common:
        vw1.vprint('COMMON %s %s' % (v1[1],v2[1]))

