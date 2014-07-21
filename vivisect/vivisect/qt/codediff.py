import os
import traceback

import vqt.tree as vq_tree

from threading import Thread
from PyQt4 import QtCore, QtGui

from vqt.main import idlethread
import vivisect.qt.main as vivqt_main
import vivisect.codediff as viv_codediff

class VQCodeDiffModel(vq_tree.VQTreeModel):
    columns = ('Name', 'Match', 'Score')

#class VQCodeDiffTree(vq_tree.VQTreeView, viv_base.VivEventCore):
class VQCodeDiffTree(vq_tree.VQTreeView):

    def __init__(self, cdiff, parent=None):
        vq_tree.VQTreeView.__init__(self, parent=parent)
        #viv_base.VivEventCore.__init__(self, vw)

        self.cdiff = cdiff
        #self.vw = vw
        #self.vwqgui = vwqgui
        #self._viv_va_nodes = {}

        #vwqgui.addEventCore(self)

        self.setWindowTitle('CodeDiff Tree')
        self.setSortingEnabled(True)

        self.setModel(VQCodeDiffModel(parent=self))

    def closeEvent(self, event):
        # FIXME this doesn't actually do anything...
        self.parentWidget().delEventCore(self)
        return vq_tree.VQTreeView.closeEvent(self, event)

    def woot(self):
        node = self.model().append(row)
        node.va = va
        self._viv_va_nodes[va] = node
        return node

class VQCodeDiffView(QtGui.QWidget):

    def __init__(self, cdiff, vqgui):
        self.cdiff = cdiff
        # assuming that the parent is GUI for vw1...

        QtGui.QWidget.__init__(self)

        self.vqgui1 = vqgui
        self.vqgui2 = vivqt_main.VQVivMainWindow(self.cdiff.vw2)
        self.vqgui2.show()

        self.difftree = VQCodeDiffTree(cdiff, self)
        self.difftree.doubleClicked.connect( self.doubleClickedSignal )

        vbox = QtGui.QVBoxLayout()
        vbox.setMargin(2)
        vbox.setSpacing(4)
        vbox.addWidget(self.difftree)
        self.setLayout(vbox)

        self.setWindowTitle('Vivisect Code Diff')
        self.show()

        v1name = cdiff.vw1.getMeta('StorageName')
        v2name = cdiff.vw2.getMeta('StorageName')

        vw1u, vw2u, vwcom = cdiff.getFunctionDeltas()

        # Calculate all the "best matches" for each of the unmatched
        v1ehashes = {}
        for fva, fname in vw1u:
            v1ehashes[fva] = viv_codediff.getFunctionEdgeList(cdiff.vw1, fva)

        v2ehashes = {}
        for fva, fname in vw2u:
            v2ehashes[fva] = viv_codediff.getFunctionEdgeList(cdiff.vw2, fva)

        v1_soft_matches = {}
        for fva, fname in vw1u:
            edgelist = v1ehashes.get(fva)
            v1_soft_matches[fva] = viv_codediff.getBestBlockMatch(edgelist, v2ehashes)

        v2_soft_matches = {}
        for fva, fname in vw2u:
            edgelist = v2ehashes.get(fva)
            v2_soft_matches[fva] = viv_codediff.getBestBlockMatch(edgelist, v1ehashes)
            
        model = VQCodeDiffModel(parent=self.difftree)

        # Put in all the vw1 uniques
        n1 = model.append((os.path.basename(v1name), '',''))

        for fva, fname in vw1u:
            bva, bscore = v1_soft_matches.get(fva)
            mname = ''
            if bva:
                mname = cdiff.vw2.getName(bva)
            node = model.append( (fname, mname, bscore), n1)
            node.expr1 = fname
            node.expr2 = mname

        # Now the vw2 uniques
        n2 = model.append((os.path.basename(v2name), '', ''))
        for fva, fname in vw2u:
            bva, bscore = v2_soft_matches.get(fva)
            mname = ''
            if bva:
                mname = cdiff.vw1.getName(bva)
            node = model.append( (fname, mname, bscore), n2)
            node.expr1 = mname
            node.expr2 = fname

        # And the common ones...
        nc = model.append(('Common To Both', '', ''))
        for (v1addr, v1name),(v2addr,v2name) in vwcom:
            model.append((v1name, v2name, '100'), nc)

        self.difftree.setModel(model)

    def doubleClickedSignal(self, idx):
        if idx.isValid():
            pnode = idx.internalPointer()
            #expr1 = pnode.rowdata[1]
            #expr2 = pnode.rowdata[2]
            expr1 = getattr(pnode, 'expr1', '')
            expr2 = getattr(pnode, 'expr2', '')

            fva1 = None
            fva2 = None

            if expr1:
                fva1 = self.cdiff.vw1.parseExpression(expr1)
                #self.vqgui1.vivNavSignal.emit(expr1)

            if expr2:
                fva2 = self.cdiff.vw2.parseExpression(expr2)
                #self.vqgui2.vivNavSignal.emit(expr2)

            if fva1 and fva2:

                bd1, bd2 = self.cdiff.getBlockDifferences(fva1, fva2)

                cmap1 = {}
                for bva, bsize, fva in bd1:
                    for i in xrange(bva, bva+bsize):
                        cmap1[i] = 'yellow'

                self.vqgui1.vivMemColorSignal.emit(cmap1)

                cmap2 = {}
                for bva, bsize, fva in bd2:
                    for i in xrange(bva, bva+bsize):
                        cmap2[i] = 'yellow'

                self.vqgui2.vivMemColorSignal.emit(cmap2)

            return True

