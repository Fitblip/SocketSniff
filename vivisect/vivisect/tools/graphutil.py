
'''
Some glue code to do workspace related things based on visgraph
'''

import envi
import vivisect
import collections
from operator import itemgetter
import visgraph.pathcore as vg_pathcore
import visgraph.graphcore as vg_graphcore

xrskip = envi.BR_PROC | envi.BR_DEREF

def getLongPath(g, maxpath=1000):
    '''
    Returns a list of list tuples (node id, edge id) representing the longest path
    '''

    todo = collections.defaultdict(list)
    allnodes = collections.defaultdict(list)
    nodes = {}

    # create default dict
    for nid, weight in sorted(g.getNodeWeights().items(), lambda x,y: cmp(y[1], x[1]) ):
        if not len(g.getRefsFrom(nid)):
            # todo is a tuple of (nid, current path, visited nodes)
            todo[weight].append( (nid, list(), set()) ) 
        nodes[ nid ] = weight 
        allnodes[weight].append( (nid, list(), set()) )

    rootnodes = set(g.getRootNodes()) 
    wmax = 0
    if len(todo):
        wmax = max( todo.keys() )

    invalidret = False
    # if the weight of the longest path to a leaf node
    # is not the highest weight then we need to fix our
    # path choices by taking the longer path 
    amax = max( allnodes.keys() )
    if wmax != amax:
        todo = allnodes 
        wmax = amax
        invalidret = True 

    pcnt = 0
    rpaths = []
    fva = g.getMeta('fva')
    # this is our loop that we want to yield out of..
    for w in xrange(wmax, -1, -1):
        # get our todo list which is at first a list of leafs..
        nleafs = todo.get(w)
        if not nleafs: 
            continue
        # todo leafs
        for nid, paths, visited in nleafs:
            tleafs= collections.defaultdict(list)
            if not paths:
                paths = [(nid, None)]
            # work is a tuple of (nid, weight, current path, visited)
            work = [(nid, w, paths, visited) ]
            while work:
                nid, weight, cpath, visited = work.pop()
                for eid, fromid, toid, einfo in g.getRefsTo(nid):
                    if fromid in visited: 
                        continue

                    nweight = nodes.get(fromid)
                    if nweight == weight-1:
                        cpath[-1] = (nid, eid)
                        cpath.append( (fromid, None) )
                        v = set(visited)
                        v.add(fromid)
                        work.append( (fromid, weight-1, list(cpath), v) ) 
                    else:
                        l = list(cpath)
                        l[-1] = (nid, eid)
                        l.append( (fromid, None) )
                        v = set(visited)
                        v.add(fromid)
                        t = (fromid, l, v) 
                        if t not in tleafs[nweight]:
                            tleafs[ nweight ].append( t )

                if nid in rootnodes: 
                    l = list(cpath)
                    l.reverse()
                    yield l

            # update our todo with our new paths to resume from 
            for nw, l in tleafs.items():
                todo[nw].extend( l )

def _nodeedge(tnode):
    nid = vg_pathcore.getNodeProp(tnode, 'nid')
    eid = vg_pathcore.getNodeProp(tnode, 'eid')
    return nid,eid

def getCoveragePaths(fgraph, maxpath=None):
    '''
    Get a set of paths which will cover every block, but will
    *end* on branches which re-merge with previously traversed
    paths.  This allows a full coverage of the graph with as
    little work as possible, but *will* omit possible states.

    Returns: yield based path generator ( where path is list if (nid,edge) tuples )
    '''
    pathcnt = 0
    nodedone = {}

    for root in fgraph.getRootNodes():

        proot = vg_pathcore.newPathNode(nid=root, eid=None)
        todo = [(root,proot), ]

        while todo:

            nodeid,cpath = todo.pop()
            refsfrom = fgraph.getRefsFrom(nodeid)

            # Record that we have visited this node...
            nodedone[nodeid] = True

            # This is a leaf node!
            if not refsfrom:
                path = vg_pathcore.getPathToNode(cpath)
                yield [ _nodeedge(n) for n in path ]

                pathcnt += 1
                if pathcnt >= maxpath:
                    return

            for eid, fromid, toid, einfo in refsfrom:

                # If we're branching to a visited node, return the path as is
                if nodedone.get(toid):
                    path = vg_pathcore.getPathToNode(cpath)
                    yield [ _nodeedge(n) for n in path ]

                    # Check if that was the last path we should yield
                    pathcnt += 1
                    if pathcnt >= maxpath:
                        return

                    # If we're at a completed node, take no further branches
                    continue

                npath = vg_pathcore.newPathNode(parent=cpath, nid=toid, eid=eid)
                todo.append((toid,npath))

def getCodePaths(fgraph, loopcnt=0, maxpath=None):
    '''
    Return a list of all the paths through the hierarchical graph.  Each
    "root" node is traced to all terminating points.  Specify a loopcnt
    to allow loop paths to be generated with the given "loop iteration count"

    Example:
        for path in getCodePaths(fgraph):
            for node,edge in path:
                ...etc...
    '''
    pathcnt = 0
    for root in fgraph.getRootNodes():
        proot = vg_pathcore.newPathNode(nid=root, eid=None)
        todo = [(root,proot), ]

        while todo:

            nodeid,cpath = todo.pop()

            refsfrom = fgraph.getRefsFrom(nodeid)

            # This is a leaf node!
            if not refsfrom:
                path = vg_pathcore.getPathToNode(cpath)
                yield [ _nodeedge(n) for n in path ]

                pathcnt += 1
                if maxpath and pathcnt >= maxpath:
                    return

            for eid, fromid, toid, einfo in refsfrom:
                # Skip loops if they are "deeper" than we are allowed
                if vg_pathcore.getPathLoopCount(cpath, 'nid', toid) > loopcnt:
                    continue

                npath = vg_pathcore.newPathNode(parent=cpath, nid=toid, eid=eid)
                todo.append((toid,npath))

def getLoopPaths(fgraph):
    '''
    Similar to getCodePaths(), however, getLoopPaths() will return path lists
    which loop.  The last element in the (node,edge) list will be the first
    "looped" block.
    '''
    loops = []
    for root in fgraph.getRootNodes():
        proot = vg_pathcore.newPathNode(nid=root, eid=None)
        todo = [ (root,proot), ]

        while todo:
            nodeid,cpath = todo.pop()

            for eid, fromid, toid, einfo in fgraph.getRefsFrom(nodeid):

                loopcnt = vg_pathcore.getPathLoopCount(cpath, 'nid', toid)
                if loopcnt > 1:
                    continue

                npath = vg_pathcore.newPathNode(parent=cpath, nid=toid, eid=eid)
                if loopcnt == 1:
                    loops.append(npath)
                else:
                    todo.append((toid,npath))

    for lnode in loops:
        yield [ _nodeedge(n) for n in vg_pathcore.getPathToNode(lnode) ]

def buildFunctionGraph(vw, fva, revloop=False):
    '''
    Build a visgraph HierarchicalGraph for the specified function.
    '''

    g = vg_graphcore.HierarchicalGraph()
    g.setMeta('fva', fva)

    colors = vw.getFunctionMeta(fva, 'BlockColors', default={})
    fcb = vw.getCodeBlock(fva)
    if fcb == None:
        t = (fva, vw.isFunction(fva))
        raise Exception('Invalid initial code block for 0x%.8x isfunc: %s' % t)

    todo = [ (fcb, []), ]

    fcbva, fcbsize, fcbfunc = fcb

    # Add the root node...
    bcolor = colors.get(fva, '#0f0')
    g.addNode(nodeid=fva, rootnode=True, cbva=fva, cbsize=fcbsize, color=bcolor)

    while todo:

        (cbva,cbsize,cbfunc),path = todo.pop()

        path.append(cbva)

        # If the code block va doesn't have a node yet, make one
        if not g.hasNode(cbva):
            bcolor = colors.get(cbva, '#0f0')
            g.addNode(nodeid=cbva, cbva=cbva, cbsize=cbsize, color=bcolor)

        # Grab the location for the last instruction in the block
        lva, lsize, ltype, linfo = vw.getLocation(cbva+cbsize-1)

        for xrfrom, xrto, xrtype, xrflags in vw.getXrefsFrom(lva, vivisect.REF_CODE):

            # For now, the graph doesn't cross function boundaries
            # or indirects.
            if xrflags & xrskip:
                continue

            if not g.hasNode(xrto):
                cblock = vw.getCodeBlock(xrto)
                if cblock == None:
                    print 'CB == None in graph building?!?!'
                    print '(fva: 0x%.8x cbva: 0x%.8x)' % (fva, xrto)
                    continue

                tova, tosize, tofunc = cblock
                if tova != xrto:
                    print 'CBVA != XREFTO in graph building!?'
                    print '(cbva: 0x%.8x xrto: 0x%.8x)' % (tova, xrto)
                    continue

                # Since we haven't seen this node, lets add it to todo
                # and build a new node for it.
                todo.append( ((tova,tosize,tofunc), list(path)) )
                bcolor = colors.get(tova, '#0f0')
                g.addNode(nodeid=tova, cbva=tova, cbsize=tosize, color=bcolor)

            # If they want it, reverse "loop" edges (graph layout...)
            if revloop and xrto in path:
                g.addEdge(xrto, cbva, reverse=True)
            else:
                g.addEdge(cbva, xrto)
                
        if ltype == vivisect.LOC_OP and linfo & envi.IF_NOFALL:
            continue

        # If this codeblock can fall through into another, add it to
        # todo!
        fallva = lva + lsize
        if not g.hasNode(fallva):
            fallblock = vw.getCodeBlock(fallva)
            if fallblock == None:
                print 'FB == None in graph building!??!'
                print '(fva: 0x%.8x  fallva: 0x%.8x' % (fva, fallva)
            elif fallva != fallblock[0]:
                print 'FALLVA != CBVA in graph building!??!'
                print '(fallva: 0x%.8x CBVA: 0x%.8x' % (fallva, fallblock[0])
            else:
                fbva, fbsize, fbfunc = fallblock
                if fbfunc != fva:
                    continue

                todo.append( ((fbva,fbsize,fbfunc), list(path)) )
                bcolor = colors.get(fallva, '#0f0')
                g.addNode(nodeid=fallva, cbva=fallva, cbsize=fbsize, color=bcolor)

        # If we ended up with a destination node, make the edge
        if g.hasNode(fallva):
            # If they want it, reverse "loop" edges (graph layout...)
            if revloop and fallva in path:
                g.addEdge(fallva, cbva, reverse=True)
            else:
                g.addEdge(cbva, fallva)

    return g

