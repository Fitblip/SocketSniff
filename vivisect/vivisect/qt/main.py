import os
import sys

import vstruct.qt as vs_qt
import envi.expression as e_expr
import envi.qt.config as e_q_config

import vqt.main as vq_main
import vqt.colors as vq_colors
import vqt.qpython as vq_python
import vqt.application as vq_app

import vivisect.cli as viv_cli
import vivisect.base as viv_base
import vivisect.vdbext as viv_vdbext
import vivisect.qt.tips as viv_q_tips
import vivisect.qt.views as viv_q_views
import vivisect.qt.memory as viv_q_memory
import vivisect.qt.remote as viv_q_remote
import vivisect.qt.ustruct as viv_q_ustruct
import vivisect.extensions as viv_extensions
import vivisect.qt.funcgraph as viv_q_funcgraph
import vivisect.qt.funcviews as viv_q_funcviews
import vivisect.qt.symboliks as viv_q_symboliks
import vivisect.remote.share as viv_share
import vivisect.remote.server as viv_server

from PyQt4 import QtCore, QtGui
from vqt.common import *
from vivisect.const import *

dock_top   = QtCore.Qt.TopDockWidgetArea
dock_right = QtCore.Qt.RightDockWidgetArea

class VQVivMainWindow(vq_app.VQMainCmdWindow, viv_base.VivEventDist):

    # Child windows may emit this on "navigate" requests...
    #vivNavSignal = QtCore.pyqtSignal(str, name='vivNavSignal') 
    vivMemColorSignal = QtCore.pyqtSignal(dict, name='vivMemColorSignal')

    def __init__(self, vw):
        self.vw = vw
        vw._viv_gui = self
        viv_base.VivEventDist.__init__(self, vw)
        vq_app.VQMainCmdWindow.__init__(self, 'Vivisect', vw)
        self.vqAddMenuField('&File.Save', self._menuFileSave)
        self.vqAddMenuField('&File.Save As', self._menuFileSaveAs)
        self.vqAddMenuField('&File.Save to Server', self._menuFileSaveServer)

        self.vqAddMenuField('&File.Quit', self.close)
        self.vqAddMenuField('&Edit.&Preferences', self._menuEditPrefs)

        self.vqAddMenuField('&View.&Exports', self._menuViewExports)
        self.vqAddMenuField('&View.&Functions', self._menuViewFunctions)
        self.vqAddMenuField('&View.&Imports', self._menuViewImports)
        self.vqAddMenuField('&View.&Names', self._menuViewNames)
        self.vqAddMenuField('&View.&Memory', self._menuViewMemory)
        self.vqAddMenuField('&View.&Function Graph', self._menuViewFuncGraph)
        self.vqAddMenuField('&View.&Strings', self._menuViewStrings)
        #self.vqAddMenuField('&View.&Strings', ACT(viv_q_views.getLocView, vw, (LOC_STRING,LOC_UNI) ,'Strings'))
        self.vqAddMenuField('&View.&Structures', self._menuViewStructs)
        self.vqAddMenuField('&View.&Segments', self._menuViewSegments)
        self.vqAddMenuField('&View.&Symboliks', self._menuViewSymboliks)
        self.vqAddMenuField('&View.&Layouts.&Save', self._menuViewLayoutsSave)
        self.vqAddMenuField('&View.&Layouts.&Load', self._menuViewLayoutsLoad)

        self.vqAddMenuField('&Share.Share Workspace', self._menuShareWorkspace)
        self.vqAddMenuField('&Share.Connect to Shared Workspace', self._menuShareConnect)
        self.vqAddMenuField('&Share.Connect To Workspace Server', self._menuShareConnectServer)

        self.vqAddMenuField('&Tools.&Python', self._menuToolsPython)
        self.vqAddMenuField('&Tools.Code Diff', self._menuToolsCodeDiff)
        self.vqAddMenuField('&Tools.&Debug', self._menuToolsDebug)
        self.vqAddMenuField('&Tools.&Structures.Add Namespace', self._menuToolsStructNames)
        self.vqAddMenuField('&Tools.&Structures.New', self._menuToolsUStructNew)
        self.vqAddDynMenu('&Tools.&Structures.&Edit', self._menuToolsUStructEdit)

        self.vqAddDynMenu('&Tools.&Va Sets', self._menuToolsVaSets)

        self.vw.vprint('Welcome to Vivisect (Qt Edition)!')
        self.vw.vprint('Random Tip: %s' % viv_q_tips.getRandomTip())

        if len(self.vqGetDockWidgets()) == 0:
            self.vw.vprint('\n')
            self.vw.vprint('Looks like you have an empty layout!')
            self.vw.vprint('Use View->Layouts->Load and select vivisect/qt/default.lyt')

        fname = os.path.basename(self.vw.getMeta('StorageName', 'Unknown'))
        self.setWindowTitle('Vivisect: %s' % fname)

    def setVaName(self, va, parent=None):
        if parent == None:
            parent = self

        name, ok = QtGui.QInputDialog.getText(parent, 'Enter...', 'Name')
        if ok:
            self.vw.makeName(va, str(name))

    def setVaComment(self, va, parent=None):
        if parent == None:
            parent = self
        comment, ok = QtGui.QInputDialog.getText(parent, 'Enter...', 'Comment')
        if ok:
            self.vw.setComment(va, str(comment))

    def setFuncLocalName(self, fva, offset, atype, aname):
        newname, ok = QtGui.QInputDialog.getText(self, 'Enter...', 'Local Name')
        if ok:
            self.vw.setFunctionLocal(fva, offset, LSYM_NAME, (atype,str(newname)))

    def setFuncArgName(self, fva, idx, atype, aname):
        newname, ok = QtGui.QInputDialog.getText(self, 'Enter...', 'Argument Name')
        if ok:
            self.vw.setFunctionArg(fva, idx, atype, str(newname))

    def showFuncCallGraph(self, fva):
        callview = viv_q_funcviews.FuncCallsView( self.vw )
        callview.functionSelected( fva )
        callview.show()
        self.vqDockWidget( callview, floating=True )

    def makeStruct(self, va, parent=None):
        if parent == None:
            parent = self
        sname = vs_qt.selectStructure(self.vw.vsbuilder, parent=parent)
        if sname != None:
            self.vw.makeStructure(va, sname)

    def addBookmark(self, va, parent=None):
        if parent == None:
            parent = self
        bname, ok = QtGui.QInputDialog.getText(parent, 'Enter...', 'Bookmark Name')
        if ok:
            self.vw.setVaSetRow('Bookmarks', (va, str(bname)))

    def _menuEditPrefs(self):
        configs = []
        configs.append(('Vivisect',self.vw.config.viv))
        configs.append(('Vdb',self.vw.config.vdb))
        self._cfg_widget = e_q_config.EnviConfigTabs(configs)
        self._cfg_widget.show()

    def _menuToolsUStructNew(self):
        u = viv_q_ustruct.UserStructEditor( self.vw )
        w = self.vqDockWidget( u, floating=True )
        w.resize( 600, 600 )

    def _menuToolsUStructEdit(self, name=None):
        if name == None:
            return self.vw.getUserStructNames()
        u = viv_q_ustruct.UserStructEditor( self.vw , name=name)
        w = self.vqDockWidget( u, floating=True )
        w.resize( 600, 600 )

    def _menuToolsVaSets(self, name=None):
        if name == None:
            return self.vw.getVaSetNames()
        view = viv_q_views.VQVivVaSetView(self.vw, self, name)
        self.vqDockWidget(view)

    def vqInitDockWidgetClasses(self):

        exprloc = e_expr.MemoryExpressionLocals(self.vw, symobj=self.vw)
        exprloc['vw'] = self.vw
        exprloc['vwqgui'] = self
        exprloc['vprint'] = self.vw.vprint

        self.vqAddDockWidgetClass(viv_q_views.VQVivExportsView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_views.VQVivFunctionsView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_views.VQVivNamesView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_views.VQVivImportsView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_views.VQVivSegmentsView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_views.VQVivStringsView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_views.VQVivStructsView, args=(self.vw, self))
        self.vqAddDockWidgetClass(vq_python.VQPythonView, args=(exprloc, self))
        self.vqAddDockWidgetClass(viv_q_memory.VQVivMemoryView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_funcgraph.VQVivFuncgraphView, args=(self.vw, self))
        self.vqAddDockWidgetClass(viv_q_symboliks.VivSymbolikFuncPane, args=(self.vw, self))

    def _menuToolsDebug(self):
        viv_vdbext.runVdb(self)

    def _menuViewFuncGraph(self):
        self.vqBuildDockWidget('VQVivFuncgraphView', area=QtCore.Qt.TopDockWidgetArea)

    def _menuViewSymboliks(self):
        self.vqBuildDockWidget('VivSymbolikFuncPane', area=QtCore.Qt.TopDockWidgetArea)

    @vq_main.workthread
    def _menuFileSave(self, fullsave=False):
        self.vw.vprint('Saving workspace...')
        self.vw.saveWorkspace(fullsave=fullsave)
        self.vw.vprint('complete!')

    def _menuFileSaveAs(self):
        fname = QtGui.QFileDialog.getSaveFileName(self, 'Save As...')
        if fname == None:
            return
        self.vw.setMeta('StorageName', fname)
        self._menuFileSave(fullsave=True)

    def _menuFileSaveServer(self):
        viv_q_remote.saveToServer(self.vw, parent=self)

    def _menuViewLayoutsLoad(self):
        fname = QtGui.QFileDialog.getOpenFileName(self, 'Load Layout')
        if fname == None:
            return

        settings = QtCore.QSettings(fname, QtCore.QSettings.IniFormat)
        self.vqRestoreGuiSettings(settings)

    def _menuViewLayoutsSave(self):
        fname = QtGui.QFileDialog.getSaveFileName(self, 'Save Layout')
        if fname == None:
            return

        settings = QtCore.QSettings(fname, QtCore.QSettings.IniFormat)
        self.vqSaveGuiSettings(settings)

    def _menuToolsStructNames(self):
        nsinfo = vs_qt.selectStructNamespace()
        if nsinfo != None:
            nsname, modname = nsinfo
            self.vw.vprint('Adding struct namespace: %s' % nsname)
            self.vw.addStructureModule(nsname, modname)

    def _menuShareWorkspace(self):
        self.vw.vprint('Sharing workspace...')
        daemon = viv_share.shareWorkspace(self.vw)
        self.vw.vprint('Workspace Listening Port: %d' % daemon.port)
        self.vw.vprint('Clients may now connect to your host on port %d' % daemon.port)

    def _menuShareConnect(self):
        viv_q_remote.openSharedWorkspace(self.vw, parent=self)

    def _menuShareConnectServer(self):
        viv_q_remote.openServerAndWorkspace(self.vw, parent=self)

    def _menuToolsCodeDiff(self):

        fname = QtGui.QFileDialog.getOpenFileName(self, 'Select Second Workspace (.viv)')
        if fname == None:
            return

        fname = str(fname)

        import vivisect.codediff as viv_codediff
        import vivisect.qt.codediff as vqt_codediff

        vw2 = viv_cli.VivCli()
        self.vw.vprint('Loading second workspace: %s...' % fname)
        vw2.loadWorkspace(fname)

        # Make our code diff guy...
        cdiff = viv_codediff.CodeDiff(self.vw, vw2)

        # Create the codediff view
        self.dview = vqt_codediff.VQCodeDiffView(cdiff, self)
        self.dview.show()

    def _menuToolsPython(self):
        self.vqBuildDockWidget('VQPythonView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewStrings(self):
        self.vqBuildDockWidget('VQVivStringsView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewStructs(self):
        self.vqBuildDockWidget('VQVivStructsView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewSegments(self):
        self.vqBuildDockWidget('VQVivSegmentsView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewImports(self):
        self.vqBuildDockWidget('VQVivImportsView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewExports(self):
        self.vqBuildDockWidget('VQVivExportsView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewFunctions(self):
        self.vqBuildDockWidget('VQVivFunctionsView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewNames(self):
        self.vqBuildDockWidget('VQVivNamesView', area=QtCore.Qt.RightDockWidgetArea)

    def _menuViewMemory(self):
        self.vqBuildDockWidget('VQVivMemoryView', area=QtCore.Qt.TopDockWidgetArea)

    @vq_main.idlethread
    def _ve_fireEvent(self, event, edata):
        return viv_base.VivEventDist._ve_fireEvent(self, event, edata)

@vq_main.idlethread
def runqt(vw, closeme=None):
    '''
    Use this API to instantiate a QT main window and show it when
    there is already a main thread running...
    '''
    mw = VQVivMainWindow(vw)
    viv_extensions.loadExtensions( vw, mw )
    mw.show()

    if closeme:
        closeme.close()

    return mw

def main(vw):
    vq_main.startup(css=vq_colors.qt_matrix)
    mw = VQVivMainWindow(vw)
    mw.show()
    viv_extensions.loadExtensions( vw, mw )
    vq_main.main()

if __name__ == '__main__':
    vw = viv_cli.VivCli()
    import sys
    if len(sys.argv) == 2:
        vw.loadWorkspace(sys.argv[1])
    main(vw)

