
from PyQt4 import QtCore, QtGui

import visgraph.renderers as vg_render

class QtGraphRenderer(vg_render.GraphRenderer, QtGui.QGraphicsView):

    def __init__(self, graph, parent=None):
        QtGui.QGraphicsView.__init__(self, parent=parent)
        vg_render.GraphRenderer.__init__(self, graph)

        scene = QtGui.QGraphicsScene(parent=self)
        self.setScene( scene )

    def setNodeSizes(self, graph):
        nodes = graph.getNodes()
        [ self._getNodeWidget(nid,nprops) for (nid,nprops) in nodes ]

    def _getNodeWidget(self, nid, ninfo):

        wid = ninfo.get('widget')
        if wid == None:
            rep = ninfo.get('repr')
            if rep == None:
                rep = 'node: %s' % nid

            wid = QtGui.QLabel( rep )
            ninfo['widget'] = wid

        gproxy = ninfo.get('gproxy')
        if gproxy == None:
            gproxy = self.scene().addWidget( wid )
            # Nodes always get drawn on top!
            gproxy.setZValue( 1.0 )
            ninfo['gproxy'] = gproxy
            geom = gproxy.geometry()
            ninfo['size'] = ( int(geom.width()), int(geom.height()) )

        return gproxy

    def renderEdge(self, eid, einfo, points):
        scene = self.scene()

        # If we have been drawn already, get rid of it.
        gproxy = einfo.get('gproxy')
        if gproxy:
            scene.removeItem(gproxy)

        qpoints = [ QtCore.QPointF( x, y ) for ( x, y ) in points ]
        qpoly = QtGui.QPolygonF( qpoints )

        ecolor = self._vg_graph.getMeta('edgecolor', '#000')
        ecolor = einfo.get('color', ecolor)

        pen = QtGui.QPen( QtGui.QColor( ecolor ) )
        gproxy = self.scene().addPolygon( qpoly, pen=pen )

        einfo['gproxy'] = gproxy

    def renderNode(self, nid, ninfo, xpos, ypos):

        scene = self.scene()

        gproxy = self._getNodeWidget( nid, ninfo )

        x,y = ninfo.get('position')
        w,h = ninfo.get('size')

        #print 'POS',ninfo['position']
        #print 'SIZE',ninfo['size']

        geom = gproxy.geometry()
        #print 'GEOM',geom
        geom.moveTo(x-(w/2),y-(h/2))
        gproxy.setGeometry( geom )

def stuff():
    print 'stuff'

if __name__ == '__main__':

    import vqt.main
    import vqt.basics

    import visgraph.graphcore as vg_graphcore
    import visgraph.layouts.force as vg_force
    import visgraph.layouts.dynadag as vg_dynadag
    import visgraph.renderers.qtrend as vg_qtrend

    g = vg_graphcore.HierarchicalGraph()

    g.addNode('A', rootnode=True)
    g.addNode('B')
    g.addNode('C')
    g.addNode('D')

    g.addNode('E')
    g.addNode('F')
    g.addNode('G')

    g.addEdge('A','B')
    g.addEdge('A','C')

    g.addEdge('B','D')
    g.addEdge('B','E')

    g.addEdge('C','F')
    g.addEdge('C','G')

    import pprint

    vqt.main.startup()

    layout = vg_force.ForceLayout(g)

    # TOTAL HACK TO MAKE THE layoutGraph() routine only loop
    # once per "tick"
    layout._f_minforce = 999999999

    rend = vg_qtrend.QtGraphRenderer( g, parent=None )

    def woot():
        layout.renderGraph(rend)

    # Make a timer that will tick the physics engine
    timer = QtCore.QTimer()
    timer.setInterval( 200 )
    timer.timeout.connect( woot )

    def delNode(nid,nprops):
        scene = rend.scene()
        scene.removeItem( nprops['gproxy'] )
        [ scene.removeItem( einfo['gproxy'] ) for (eid,n1,n2,einfo) in g.getRefsTo( nid ) ]
        [ scene.removeItem( einfo['gproxy'] ) for (eid,n1,n2,einfo) in g.getRefsFrom( nid ) ]
        g.delNode( nid )

    xr = iter(xrange(10000))

    def expNode(nid,nprops):
        n2id = xr.next()
        g.addNode( n2id )
        n2props = g.getNodeProps( n2id )
        n2props['widget'] = QtGui.QPushButton('new: %s' % n2id)
        #x,y = nprops['position']
        #n2props['position'] = (x+30, y+30)
        g.addEdge(nid, n2id)
        rend._getNodeWidget( n2id, n2props )
        #nextnid += 1
        layout.renderGraph(rend)

    for nid,nprops in g.getNodes():
        b = QtGui.QPushButton('N: %s' % nid)
        b.clicked.connect( vqt.basics.ACT( delNode, nid, nprops ) )
        b.setToolTip( pprint.pformat( nprops ) )
        nprops['widget'] = b

    #layout.renderGraph(rend)
    rend.show()
    geom = rend.geometry()
    geom.setWidth(800)
    geom.setHeight(600)
    rend.setGeometry(geom)
    timer.start()

    vqt.main.main()

