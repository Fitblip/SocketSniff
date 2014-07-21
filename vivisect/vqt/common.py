# Some common GUI helpers
from PyQt4 import QtGui,QtCore

class ACT:
    def __init__(self, meth, *args, **kwargs):
        self.meth = meth
        self.args = args
        self.kwargs = kwargs

    def __call__(self):
        return self.meth( *self.args, **self.kwargs )

class VqtModel(QtCore.QAbstractItemModel):

    columns = ('one','two')
    editable = None
    dragable = False

    def __init__(self, rows=()):
        QtCore.QAbstractItemModel.__init__(self)
        # Make sure the rows are lists ( so we can mod them )
        self.rows = [ list(row) for row in rows ]
        if self.editable == None:
            self.editable = [False,] * len(self.columns)

    def index(self, row, column, parent):
        return self.createIndex(row, column, self.rows[row])

    def parent(self, index):
        return QtCore.QModelIndex()

    def rowCount(self, index):
        if index.internalPointer() in self.rows:
            return 0
        return len(self.rows)

    def data(self, index, role):
        if role == 0: 
            row = index.row()
            col = index.column()
            return self.rows[row][col]

        else:
            return None

    def columnCount(self, index):
        return len(self.columns)

    def headerData(self, column, orientation, role):

        if ( orientation == QtCore.Qt.Horizontal and
             role == QtCore.Qt.DisplayRole):

            return self.columns[column]

        return None

    def flags(self, index):
        if not index.isValid():
            return 0
        flags = QtCore.QAbstractItemModel.flags(self, index)
        col = index.column()
        if self.editable[col]:
            flags |= QtCore.Qt.ItemIsEditable

        if self.dragable:
            flags |= QtCore.Qt.ItemIsDragEnabled# | QtCore.Qt.ItemIsDropEnabled

        return flags

    #def data(self, index, role):
        #if not index.isValid():
            #return None
        #item = index.internalPointer()
        #if role == QtCore.Qt.DisplayRole:
            #return item.data(index.column())
        #if role == QtCore.Qt.UserRole:
            #return item
        #return None

    #def _vqt_set_data(self, row, col, value):
        #return False

    #def appends(self, rows):

    def append(self, row):
        #pidx = self.createIndex(parent.row(), 0, parent)
        i = len(self.rows)
        idx = QtCore.QModelIndex()
        self.beginInsertRows(idx, i, i)
        self.rows.append( row )
        #node = parent.append(rowdata)
        self.endInsertRows()
        self.layoutChanged.emit()

    def setData(self, index, value, role=QtCore.Qt.EditRole):

        if not index.isValid():
            return False

        # If this is the edit role, fire the vqEdited thing
        if role == QtCore.Qt.EditRole:
            print('EDIT ROLE')
            
            #value = self.vqEdited(node, index.column(), value)
            #if value == None:
                #return False

            row = index.row()
            col = index.column()
            if not self._vqt_set_data( row, col, value ):
                return False

        return True

    #def mimeTypes(self):
        #types = QtCore.QStringList()
        #types.append('vqt/row')
        #return types

    #def mimeData(self, idx):
        #nodes = [ self.rows[i.row()][-1] for i in idx ]
        #mdata = QtCore.QMimeData()
        #mdata.setData('vqt/rows',json.dumps(nodes))
        #return mdata

class VqtView(QtGui.QTreeView):

    def __init__(self, parent=None):
        QtGui.QTreeView.__init__(self, parent=parent)
        self.setAlternatingRowColors( True )
        self.setSortingEnabled( True )

    def getSelectedRows(self):
        ret = []
        rdone = {}
        model = self.model()
        for idx in self.selectedIndexes():

            if rdone.get(idx.row()):
                continue

            rdone[idx.row()] = True
            ret.append( model.mapToSource(idx).internalPointer() )

        return ret

    def setModel(self, model):
        smodel = QtGui.QSortFilterProxyModel(parent=self)
        smodel.setSourceModel(model)
        ret = QtGui.QTreeView.setModel(self, smodel)
        c = len(model.columns)
        for i in xrange(c):
            self.resizeColumnToContents(i)
        return ret

    def getModelRows(self):
        return self.model().sourceModel().rows

    def getModelRow(self, idx):
        idx = self.model().mapToSource(idx)
        return idx.row(),idx.internalPointer()