
import envi
import envi.qt as envi_qt
import envi.bits as e_bits
import envi.qt.memory as e_mem_qt
import envi.qt.memcanvas as e_mem_canvas

import vstruct.qt as vs_qt

import vqt.main as vq_main
import vqt.hotkeys as vq_hotkey
import vqt.menubuilder as vq_menu

import vivisect.base as viv_base
import vivisect.renderers as viv_rend
import vivisect.qt.views as viv_q_views
import vivisect.qt.ctxmenu as viv_q_ctxmenu
import vivisect.qt.funcviews as viv_q_funcviews

from PyQt4          import QtCore, QtGui, QtWebKit
from envi.threads   import firethread

from vqt.main import *
from vivisect.const import *

# FIXME HACK where do these really live?
qt_horizontal   = 1
qt_vertical     = 2

def cmpoffset(x,y):
    return cmp(x[0], y[0])

class VivCanvasBase(vq_hotkey.HotKeyMixin, e_mem_canvas.VQMemoryCanvas):

    def __init__(self, *args, **kwargs):

        e_mem_canvas.VQMemoryCanvas.__init__(self, *args, **kwargs)
        vq_hotkey.HotKeyMixin.__init__(self)

        self.vw = self.mem
        self._last_sname = None

        self.addHotKey('c','viv:make:code')
        self.addHotKey('f','viv:make:function')
        self.addHotKey('s','viv:make:string')
        self.addHotKey('p','viv:make:pointer')
        self.addHotKey('u','viv:make:unicode')
        self.addHotKey('n','viv:setname')
        self.addHotKey(';','viv:comment')
        self.addHotKey('S','viv:make:struct')
        self.addHotKey('ctrl+S','viv:make:struct:again')
        self.addHotKey('U','viv:undefine')
        self.addHotKey('ctrl+s','viv:save')
        self.addHotKey('B', 'viv:bookmark')

        self.addHotKey('down','viv:nav:nextva')
        self.addHotKey('up','viv:nav:prevva')

        self.loadHotKeys(self.vw._viv_gui._vq_settings)

        # All extenders must implement vivColorMap
        vqtconnect(self.vivColorMap, 'viv:colormap')

    def vivColorMap(self, event, einfo):
        self._applyColorMap(einfo)

    def _applyColorMap(self, cmap):

        frame = self.page().mainFrame()
        style = frame.findFirstElement('#cmapstyle')

        rows = []
        for va,color in cmap.items():
            rows.append('.va_0x%.8x { color: #000000; background-color: %s }' % (va, color))

        style.setInnerXml('\n'.join(rows))

    @vq_hotkey.hotkey('viv:nav:nextva')
    def _hotkey_nav_nextva(self):
        if not self._canv_curva:
            return

        loc = self.vw.getLocation(self._canv_curva)
        if loc == None:
            loc = (self._canv_curva, 1, None, None)

        nextva = loc[0] + loc[1]
        self._selectVa(nextva)

    @vq_hotkey.hotkey('viv:nav:prevva')
    def _hotkey_nav_prevva(self):
        if not self._canv_curva:
            return

        loc = self.vw.getPrevLocation(self._canv_curva)
        if loc == None:
            loc = (self._canv_curva - 1, 1, None, None)

        self._selectVa(loc[0])

    @vq_hotkey.hotkey('viv:make:code')
    def _hotkey_make_code(self):
        if self._canv_curva:
            self.vw.makeCode(self._canv_curva)

    @vq_hotkey.hotkey('viv:make:function')
    def _hotkey_make_function(self):
        if self._canv_curva:
            self.vw.makeFunction(self._canv_curva)

    @vq_hotkey.hotkey('viv:make:string')
    def _hotkey_make_string(self):
        if self._canv_curva:
            self.vw.makeString(self._canv_curva)

    @vq_hotkey.hotkey('viv:make:pointer')
    def _hotkey_make_pointer(self):
        if self._canv_curva:
            self.vw.makePointer(self._canv_curva)

    @vq_hotkey.hotkey('viv:make:unicode')
    def _hotkey_make_unicode(self):
        if self._canv_curva:
            self.vw.makeUnicode(self._canv_curva)

    @vq_hotkey.hotkey('viv:undefine')
    def _hotkey_undefine(self):
        if self._canv_curva:
            self.vw.delLocation(self._canv_curva)

    @vq_hotkey.hotkey('viv:setname')
    def _hotkey_setname(self):
        if self._canv_curva:
            self.vw.getVivGui().setVaName( self._canv_curva, parent=self )

    @vq_hotkey.hotkey('viv:bookmark')
    def _hotkey_bookmark(self):
        if self._canv_curva:
            self.vw.getVivGui().addBookmark( self._canv_curva, parent=self )

    @vq_hotkey.hotkey('viv:comment')
    def _hotkey_comment(self):
        if self._canv_curva:
            self.vw.getVivGui().setVaComment( self._canv_curva, parent=self )

    @vq_hotkey.hotkey('viv:make:struct')
    def _hotkey_make_struct(self):
        if self._canv_curva:
            self._menuMakeStruct(self._canv_curva)

    @vq_hotkey.hotkey('viv:make:struct:again')
    def _hotkey_make_struct_again(self):
        if self._canv_curva:
            if self._last_sname != None:
                self.vw.makeStructure(self._canv_curva, self._last_sname)

    @firethread
    @vq_hotkey.hotkey('viv:save')
    def _hotkey_save(self, fullsave=False):
        self.vw.vprint('Saving workspace...')
        self.vw.saveWorkspace(fullsave=fullsave)
        self.vw.vprint('complete!')


class VQVivMemoryCanvas(VivCanvasBase):

    def wheelEvent(self, event):
        frame = self.page().mainFrame()

        sbcur = frame.scrollBarValue(qt_vertical)
        sbmin = frame.scrollBarMinimum(qt_vertical)
        sbmax = frame.scrollBarMaximum(qt_vertical)

        if sbcur == sbmax:

            lastva, lastsize = self._canv_rendvas[-1]
            mapva, mapsize, mperm, mfname = self.vw.getMemoryMap(lastva)
            sizeremain = (mapva + mapsize) - (lastva + lastsize)
            if sizeremain:
                self.renderMemoryAppend(min(sizeremain, 128))

        elif sbcur == sbmin:
            firstva, firstsize = self._canv_rendvas[0]
            mapva, mapsize, mperm, mfname = self.vw.getMemoryMap(firstva)
            sizeremain = firstva - mapva
            if sizeremain:
                self.renderMemoryPrepend(min(sizeremain, 128))

        return e_mem_canvas.VQMemoryCanvas.wheelEvent(self, event)

    def _clearColorMap(self):
        frame = self.page().mainFrame()
        style = frame.findFirstElement('#cmapstyle')
        style.setInnerXml('');

    def _navExpression(self, expr):
        if self._canv_navcallback:
            self._canv_navcallback(expr)

    def initMemWindowMenu(self, va, menu):
        nav = self.parent() # our parent is always a VQVivMemoryWindow (nav target)
        viv_q_ctxmenu.buildContextMenu(self.vw, va=va, menu=menu, nav=nav)

class VQVivMemoryView(e_mem_qt.VQMemoryWindow, viv_base.VivEventCore):

    def __init__(self, vw, vwqgui):
        self.vw = vw
        self.vwqgui = vwqgui

        self._leading = False
        self._following = None
        self._follow_menu = None # init'd in handler below

        e_mem_qt.VQMemoryWindow.__init__(self, vw, syms=vw, parent=vwqgui, mwname='viv')
        viv_base.VivEventCore.__init__(self, vw)

        vwqgui.addEventCore(self)
        self.mem_canvas._canv_rend_middle = True

        self.addHotKeyTarget('viv:xrefsto', self._viv_xrefsto)
        self.addHotKey('x', 'viv:xrefsto')

    def getRendToolsMenu(self):
        menu = e_mem_qt.VQMemoryWindow.getRendToolsMenu(self)
        if self.vw.server:

            leadact = QtGui.QAction('lead', menu, checkable=True)
            def leadToggle():
                self._leading = not self._leading
                # We can only follow if not leading... (deep huh? ;) )
                self._follow_menu.setEnabled( not self._leading )
                if self._leading:
                    self._following = None
                    self.vw.iAmLeader(self.mwname)
                self.updateMemWindowTitle()

            def clearFollow():
                self._following = None
                self.updateMemWindowTitle()

            leadact.toggled.connect(leadToggle)
            menu.addAction(leadact)
            self._follow_menu = menu.addMenu('Follow..')
            self._follow_menu.addAction('(disable)', clearFollow)

        return menu

    def getExprTitle(self):
        title = str(self.addr_entry.text())

        try:

            va = self.vw.parseExpression(title)
            name = self.vw.getName(va)
            if name != None:
                title = name

        except Exception, e:
            title = 'expr error'

        if self._leading:
            title += ' (leading)'

        if self._following != None:
            user,window = self._following
            title += ' (following %s %s)' % (user,window)

        return title

    def initMemoryCanvas(self, memobj, syms=None):
        return VQVivMemoryCanvas(memobj, syms=syms, parent=self)

    def _viv_xrefsto(self):

        if self.mem_canvas._canv_curva:
            xrefs = self.vw.getXrefsTo(self.mem_canvas._canv_curva)
            if len(xrefs) == 0:
                self.vw.vprint('No xrefs found!')
                return

            title = 'Xrefs To: 0x%.8x' % self.mem_canvas._canv_curva
            view = viv_q_views.VQXrefView(self.vw, self.vwqgui, xrefs=xrefs, title=title)
            dock = self.vwqgui.vqDockWidget(view, floating=True)
            dock.resize(800,600)

    def loadDefaultRenderers(self):

        import envi.memcanvas.renderers as e_render

        # FIXME check endianness
        self.mem_canvas.addRenderer("bytes",    e_render.ByteRend())
        self.mem_canvas.addRenderer("u_int_16", e_render.ShortRend())
        self.mem_canvas.addRenderer("u_int_32", e_render.LongRend())
        self.mem_canvas.addRenderer("u_int_64", e_render.QuadRend())

        vivrend = viv_rend.WorkspaceRenderer(self.vw)
        self.mem_canvas.addRenderer('Viv', vivrend)
        self.mem_canvas.setRenderer('Viv')

    def _updateFunction(self, fva):
        for cbva, cbsize, cbfva in self.vw.getFunctionBlocks(fva):
            self.mem_canvas.renderMemoryUpdate(cbva, cbsize)

    def VTE_IAMLEADER(self, vw, event, einfo):
        user,followname = einfo

    def VWE_SYMHINT(self, vw, event, einfo):
        va, idx, hint = einfo
        self.mem_canvas.renderMemoryUpdate(va, 1)

    def VWE_ADDLOCATION(self, vw, event, einfo):
        va,size,ltype,tinfo = einfo
        self.mem_canvas.renderMemoryUpdate(va, size)

    def VWE_DELLOCATION(self, vw, event, einfo):
        va,size,ltype,tinfo = einfo
        self.mem_canvas.renderMemoryUpdate(va, size)

    def VWE_ADDFUNCTION(self, vw, event, einfo):
        va,meta = einfo
        self.mem_canvas.renderMemoryUpdate(va, 1)

    def VWE_SETFUNCMETA(self, vw, event, einfo):
        fva, key, val = einfo
        self._updateFunction(fva)

    def VWE_SETFUNCARGS(self, vw, event, einfo):
        fva, fargs = einfo
        self._updateFunction(fva)

    def VWE_COMMENT(self, vw, event, einfo):
        va,cmnt = einfo
        self.mem_canvas.renderMemoryUpdate(va, 1)

    @idlethread
    def VWE_SETNAME(self, vw, event, einfo):
        va,name = einfo
        self.mem_canvas.renderMemoryUpdate(va, 1)
        for fromva,tova,rtype,rflag in self.vw.getXrefsTo(va):
            self.mem_canvas.renderMemoryUpdate(fromva, 1)

    @idlethread
    def VTE_IAMLEADER(self, vw, event, einfo):
        user,fname = einfo
        def setFollow():
            self._following = einfo
            self.updateMemWindowTitle()

        self._follow_menu.addAction('%s - %s' % (user,fname), setFollow)

    @idlethread
    def VTE_FOLLOWME(self, vw, event, einfo):
        user,fname,expr = einfo
        if self._following != (user,fname):
            return
        self.enviNavGoto(expr)

    @idlethread
    def enviNavGoto(self, expr, sizeexpr='256', rend=''):
        if self._leading:
            self.vw.followTheLeader(str(self.mwname), str(expr))
        return e_mem_qt.VQMemoryWindow.enviNavGoto(self, expr, sizeexpr=sizeexpr, rend=rend)

