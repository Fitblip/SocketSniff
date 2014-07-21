"""
PE Extended analysis module.
"""

import vivisect
import envi.bits as e_bits

def analyze(vw):
    """
    """
    # Go through the relocations and create locations for them
    for segva,segsize,segname,segfname in vw.getSegments():

        # FIXME should we do this by something other than name?
        if segname != ".reloc":
            continue

        offset, bytes = vw.getByteDef(segva)

        while offset < segsize:
            basepage = e_bits.parsebytes(bytes, offset, 4)

            vaoff = segva + offset
            vw.makeNumber(vaoff, 4)
            vw.makeName(vaoff, "reloc_chunk_%.8x" % vaoff)

            recsize = e_bits.parsebytes(bytes, offset+4, 4)
            vw.makeNumber(segva+offset+4, 4)

            ioff = offset + 8
            while ioff < offset+recsize:
                vw.makeNumber(segva + ioff, 2)
                ioff += 2

            offset += recsize
            if recsize == 0:
                break


