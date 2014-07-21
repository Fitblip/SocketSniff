import sys
sys.path.insert(0,"vivisect/")

import vtrace
import vdb
import PE as PE
import platform
import struct

if "32" in platform.architecture()[0]:
    from envi.archs import i386 as arch
else:
    from envi.archs import amd64 as arch

from helpers import AF_Types, Sock_Types, Protocol_Types

recv_buffers = []
sent_buffers = []

def do_format(byte):
    for bad_char in ["\x00", ".", "\t", "\n", "\r", "\xff"]:
        if byte == bad_char:
            byte = "."
    return byte

class CustomNotifier(vtrace.Notifier):
    # Event is one of the vtrace.NOTIFY_* things listed under vtrace

    def notify(self, event, trace):
        if event == vtrace.NOTIFY_BREAK:
            EIP = trace.getRegister(arch.REG_EIP)
            ESP = trace.getRegister(arch.REG_ESP)
            current_socket = trace.getMeta('current_socket')
            sockets        = trace.getMeta('sockets')
            recv_bufs      = trace.getMeta('recv_bufs')

            if not trace.getSymByAddr(EIP) and current_socket:
                if EIP == current_socket['return_pointer']:
                    # We found our break. Read EAX and finish our socket construction.
                    
                    trace.removeBreakpoint(trace.breakpoints[EIP].id)
                    
                    descriptor = trace.getRegister(arch.REG_EAX)
                    current_socket['descriptor'] = descriptor
                    sockets[descriptor] = current_socket
                    trace.setMeta('sockets', sockets)
                    trace.setMeta('current_socket', {})

            elif EIP in [x[0] for x in recv_bufs]:
                recv_bufs = trace.getMeta('recv_bufs')
                trace.removeBreakpoint(trace.breakpoints[EIP].id)
                return_pointer, socket_descriptor, output_buffer, length_to_read = [x for x in recv_bufs if x[0] == EIP][0]
                data = trace.readMemory(output_buffer, length_to_read)
                
                # import ipdb; ipdb.set_trace()
                recv_buffers.append(data)
                print "[+] Recieved buffer with length %d at 0x%08x" % (length_to_read, output_buffer)
                print "==== DATA ===="
                #print " ".join("{:02x}".format(ord(byte)) for byte in data)
                for line in [data[i:i+16] for i in xrange(0, len(data), 16)]:
                    hex_part = " ".join("{:02x}".format(ord(byte)) for byte in line)
                    ascii_part = "".join([do_format(x) for x in line])
                    if len(line) != 16:
                        hex_part += ("   " * (16 - len(line)))
                    print hex_part + " |" + ascii_part + "|"
                print "==============\n"
                # import ipdb; ipdb.set_trace()

            # TODO: Race condition if 2 sockets get allocated near-simultaniously
            elif trace.getSymByAddr(EIP).name == "socket":
                current_socket['return_pointer'] = struct.unpack("<L", trace.readMemory(ESP,4))[0]
                current_socket['af_type']        = AF_Types[struct.unpack("<L", trace.readMemory(ESP+4,4))[0]]
                current_socket['socket_type']    = Sock_Types[struct.unpack("<L", trace.readMemory(ESP+8,4))[0]]
                current_socket['protocol']       = Protocol_Types[struct.unpack("<L", trace.readMemory(ESP+12,4))[0]]
                # Add a breakpoint to our return pointer location so we can retrieve the socket descriptor in the next
                # function
                trace.addBreakByAddr(current_socket['return_pointer'])
                trace.setMeta('current_socket', current_socket)

            elif trace.getSymByAddr(EIP).name == "connect":
                conn_array = trace.getMeta('connections')
                pointer_to_sockaddr = struct.unpack("<L", trace.readMemory(ESP+8,4))[0]
                connection_info = {
                    "socket_descriptor"   : struct.unpack("<L", trace.readMemory(ESP+4,4))[0],
                    "pointer_to_sockaddr" : pointer_to_sockaddr,
                    "sa_family"           : AF_Types[struct.unpack("<H", trace.readMemory(pointer_to_sockaddr,2))[0]],
                    "port"                : struct.unpack(">H",trace.readMemory(pointer_to_sockaddr + 2,2))[0],
                    "ip_to"               : ".".join([str(ord(byte)) for byte in trace.readMemory(pointer_to_sockaddr + 4,4)])
                }
                conn_array.append(connection_info)
                trace.setMeta('connections', conn_array)
                print "[+] Connected to %s:%d" % (connection_info['ip_to'], connection_info['port'])
        
            elif trace.getSymByAddr(EIP).name == "send":
                socket_descriptor = struct.unpack("<L", trace.readMemory(ESP+4,4))[0]
                pointer_to_data   = struct.unpack("<L", trace.readMemory(ESP+8,4))[0]
                length_of_data    = struct.unpack("<L", trace.readMemory(ESP+12,4))[0]
                data = trace.readMemory(pointer_to_data, length_of_data)
                #if len(data) > 5:
                #    import IPython; IPython.embed()
                print "[+] Sent buffer with length %d at 0x%08x" % (length_of_data, pointer_to_data)
                print "==== DATA ===="
                for line in [data[i:i+16] for i in xrange(0, len(data), 16)]:
                    hex_part = " ".join("{:02x}".format(ord(byte)) for byte in line)
                    ascii_part = "".join([do_format(x) for x in line])
                    if len(line) != 16:
                        hex_part += ("   " * (16 - len(line)))
                    print hex_part + " |" + ascii_part + "|"
                print "==============\n"
                sent_buffers.append(data)
           
            elif trace.getSymByAddr(EIP).name == "recv":
                return_pointer = struct.unpack("<L", trace.readMemory(ESP,4))[0]
                socket_descriptor = struct.unpack("<L", trace.readMemory(ESP+4,4))[0]
                output_buffer = struct.unpack("<L", trace.readMemory(ESP+8,4))[0]
                length_to_read = struct.unpack("<L", trace.readMemory(ESP+12,4))[0]
                trace.addBreakByAddr(return_pointer)
                recv_bufs = trace.getMeta('recv_bufs')
                recv_bufs.append((return_pointer, socket_descriptor, output_buffer, length_to_read))
                trace.setMeta('recv_bufs', recv_bufs)
            
        trace.runAgain()


filepath = "C:\\program files\\FileZilla FTP Client\\filezilla.exe"

trace = vtrace.getTrace()
trace.execute(filepath)
    
trace.setMeta('sockets', {})
trace.setMeta('current_socket', {})
trace.setMeta('connections', [])
trace.setMeta('recv_bufs', [])

notif = CustomNotifier()
event = vtrace.NOTIFY_BREAK
trace.registerNotifier(event, notif)

lib_ws2_32 = trace.getSymByName('ws2_32')

send       = lib_ws2_32.getSymByName('send')
recv       = lib_ws2_32.getSymByName('recv')
connect    = lib_ws2_32.getSymByName('connect')
socket     = lib_ws2_32.getSymByName('socket')


breakpoints = [
    vtrace.Breakpoint(send.value),
    vtrace.Breakpoint(recv.value),
    vtrace.Breakpoint(connect.value),
    vtrace.Breakpoint(socket.value),
]

for breakpoint in breakpoints:
    trace.addBreakpoint(breakpoint)

try:
    trace.run()
except:
    pass