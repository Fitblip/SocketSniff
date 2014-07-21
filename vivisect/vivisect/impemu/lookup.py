'''
Home for the registered emulators of different types...
'''
import vivisect.impemu.platarch.i386 as v_i_i386
import vivisect.impemu.platarch.amd64 as v_i_amd64
import vivisect.impemu.platarch.windows as v_i_windows

workspace_emus  = {
    'i386'  :v_i_i386.i386WorkspaceEmulator,
    'amd64' :v_i_amd64.Amd64WorkspaceEmulator,
    ('windows','i386'):v_i_windows.Windowsi386Emulator,
}
