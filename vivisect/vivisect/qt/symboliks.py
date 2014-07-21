import vqt.tree as vq_tree
import vqt.saveable as vq_save
import envi.qt.memory as e_q_memory
import envi.qt.memcanvas as e_q_memcanvas
import vivisect.qt.ctxmenu as v_q_ctxmenu
import vivisect.symboliks.common as viv_sym_common
import vivisect.symboliks.effects as viv_sym_effects
import vivisect.symboliks.analysis as viv_sym_analysis

from PyQt4 import QtGui,QtCore

from vqt.main import *
from vqt.basics import *
from vivisect.const import *

class VivSymbolikPathsModel(vq_tree.VQTreeModel):
    columns = ('Path','Effect Count')

class VivSymbolikPathsView(vq_tree.VQTreeView):

    pathSelected = QtCore.pyqtSignal( object, object )

    def __init__(self, vw, parent=None):
        vq_tree.VQTreeView.__init__(self, parent=parent)
        self.setModel( VivSymbolikPathsModel( parent=self ) )

    def loadSymbolikPaths(self, paths):
        model = VivSymbolikPathsModel( parent=self )
        for i, (emu,effects) in enumerate(paths):
            model.append( (str(i), len(effects), emu, effects) )
        self.setModel(model)

    def selectionChanged(self, selected, unselected):

        indexes = selected.indexes()
        if indexes:
            index = indexes[0]
            rowdata = index.internalPointer().rowdata
            emu = rowdata[-2]
            path = rowdata[-1]
            self.pathSelected.emit(emu,path)

import itertools
#FIXME

class VivSymbolikFuncPane(e_q_memory.EnviNavMixin, vq_save.SaveableWidget, QtGui.QWidget):

    viewidx = itertools.count()

    def __init__(self, vw, parent=None):
        self.vw = vw
        self.fva = None
        self.vwgui = vw.getVivGui()

        self.symctx = viv_sym_analysis.getSymbolikAnalysisContext(vw)
        if self.symctx == None:
            raise Exception('No Symboliks For: %s (yet)' % vw.getMeta('Architecture'))

        self.symctx.consolve = True

        QtGui.QWidget.__init__(self, parent=parent)
        e_q_memory.EnviNavMixin.__init__(self)
        self.setEnviNavName('Symboliks%d' % self.viewidx.next())

        self.exprtext = QtGui.QLineEdit(parent=self)
        self.pathview = VivSymbolikPathsView(vw, parent=self)
        self.memcanvas = e_q_memcanvas.VQMemoryCanvas(vw, syms=vw, parent=self)

        self.pathview.pathSelected.connect(self.symPathSelected)
        self.exprtext.returnPressed.connect(self.renderSymbolikPaths)

        mainbox = VBox( self.exprtext, self.pathview, self.memcanvas )
        self.setLayout(mainbox)
        self.updateWindowTitle()

    def updateWindowTitle(self):
        ename = self.getEnviNavName()
        expr = str(self.exprtext.text())
        self.setWindowTitle('%s: %s' % (ename,expr))

    def enviNavGoto(self, expr, sizeexpr=None):
        self.exprtext.setText(expr)
        self.renderSymbolikPaths()
        self.updateWindowTitle()

    def vqGetSaveState(self):
        return { 'expr':str(self.exprtext.text()), }

    def vqSetSaveState(self, state):
        self.exprtext.setText( state.get('expr','') )
        self.renderSymbolikPaths()

    def renderSymbolikPaths(self):
        try:

            self.memcanvas.clearCanvas()
            expr = str(self.exprtext.text())
            if not expr:
                return

            va = self.vw.parseExpression(expr)
            self.fva = self.vw.getFunction(va)
            if self.fva == None:
                raise Exception('Invalid Address: 0x%.8x' % va )

            paths = self.symctx.getSymbolikPaths(self.fva, maxpath=100)
            self.pathview.loadSymbolikPaths(paths)

        except Exception, e:
            self.memcanvas.addText('ERROR: %s' % e)

    def addVivNames(self, symobj, ctx):

        emu,symctx = ctx

        width = emu.__width__ # FIXME factory thing?

        if isinstance(symobj, viv_sym_common.Const):
            loc = self.vw.getLocation(symobj.value)
            if loc and loc[2] == LOC_STRING:
                s = repr(self.vw.readMemory(loc[0], loc[1]))
                s = '"%s"' % s[1:-1]
                return viv_sym_common.Var(s, width)

            if emu.isLocalMemory(symobj, solvedval=symobj.value):
                offset = emu.getLocalOffset(symobj, solvedval=symobj.value)
                ltype,lname = self.vw.getFunctionLocal( self.fva, offset )
                if lname:
                    return viv_sym_common.Var('%s%d' % (lname, abs(offset)), width)

            if loc and loc[2] == LOC_UNI:
                buf = self.vw.readMemory(loc[0], loc[1])
                return viv_sym_common.Var('L"%s"' % buf.decode('utf-16le','ignore'), width)

            name = self.vw.getName(symobj.value)
            if name != None:
                symobj = viv_sym_common.Var(name, width)

        return symobj

    def symPathSelected(self, emu, effects):
        self.memcanvas.clearCanvas()
        colormap = {}
        for effect in effects:

            colormap[effect.va] = 'yellow'

            effect.reduce(emu)

            if isinstance(effect, viv_sym_effects.ConstrainPath) or isinstance(effect, viv_sym_effects.CallFunction):
                effect.walkTree(self.addVivNames, ctx=(emu, self.symctx))
                self.memcanvas.addVaText('0x%.8x: ' % effect.va, effect.va)
                self.memcanvas.addText( str(effect) + '\n' )
                continue

            if isinstance(effect, viv_sym_effects.WriteMemory):
                if not emu.isLocalMemory(effect.symaddr):
                    effect.walkTree(self.addVivNames, ctx=(emu, self.symctx))
                    self.memcanvas.addVaText('0x%.8x: ' % effect.va, effect.va)
                    self.memcanvas.addText( str(effect) + '\n' )
                continue

        vqtevent('viv:colormap', colormap)

        retsym = emu.getFunctionReturn()
        retsym = retsym.reduce()

        self.memcanvas.addText('RETURNS: %s\n' % retsym)

