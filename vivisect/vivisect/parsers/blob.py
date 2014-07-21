import envi
import vivisect
import vivisect.parsers as v_parsers
from vivisect.const import *

def parseFile(vw, filename):

    arch = vw.config.viv.parsers.blob.arch
    baseaddr = vw.config.viv.parsers.blob.baseaddr

    try:
        envi.getArchModule(arch)
    except Exception, e:
        raise Exception('Blob loader *requires* arch option (-O viv.parsers.blob.arch="<archname>")')


    vw.setMeta('Architecture', arch)
    vw.setMeta('Platform','unknown')
    vw.setMeta('Format','blob')

    fname = vw.addFile(filename, baseaddr, v_parsers.md5File(filename))
    vw.addMemoryMap(baseaddr, 7, filename, file(filename, "rb").read())

def parseMemory(vw, memobj, baseaddr):
    va,size,perms,fname = memobj.getMemoryMap(baseaddr)
    if not fname:
        fname = 'map_%.8x' % baseaddr
    bytes = memobj.readMemory(va, size)
    fname = vw.addFile(fname, baseaddr, v_parsers.md5Bytes(bytes))
    vw.addMemoryMap(va, perms, fname, bytes)

