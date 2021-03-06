import vdb

defconfig = {
    'viv':{

        'SymbolCacheSave':True,

        'parsers':{
            'pe':{
                'loadresources':False,
            },
            'elf':{
            },
            'blob':{
                'arch':'',
                'baseaddr':0x20200000,
            },
            'macho':{
                'baseaddr':0x70700000,
                'fatarch':'',
            },
            'ihex':{
                'arch':'',
            },
        },
        'analysis':{
            'pointertables':{
                'table_min_len':4,
            },
        },
    },
    'cli':vdb.defconfig.get('cli'), # FIXME make our own...
    'vdb':vdb.defconfig.get('vdb'),
}

defconfig.get('cli').update(vdb.defconfig.get('cli'))

# Config elements docs
docconfig = {

    'viv':{

        'SymbolCacheSave':'Save vivisect names to the vdb configured symbol cache?',

        'parsers':{
            'pe':{
                'loadresources':'Should we load resource segments?',
            },
            'elf':{
            },
            'blob':{
                'arch':'What architecture is the blob?',
                'baseaddr':'Base virtual address for loading the blob.',
            },
            'macho':{
                'baseaddr':'Base virtual address for loading the macho',
                'fatarch':'Which architecture binary to extract from a FAT macho',
            },
            'ihex':{
                'arch':'What architecture is the ihex dump?',
            },
        },

        'analysis':{
            'pointertables':{
                'table_min_len':'How many pointers must be in a row to make a table?',
            },
        },

    },

    'vdb':vdb.docconfig.get('vdb'),
}
