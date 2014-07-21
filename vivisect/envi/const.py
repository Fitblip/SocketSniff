# calling convention constants
CC_REG              = 1 << 0    # argument is stored in a register
CC_STACK            = 1 << 1    # argument is stored on the stack
CC_STACK_INF        = 1 << 2    # all following args are stored on the stack
CC_CALLEE_CLEANUP   = 1 << 3    # callee cleans up the stack
CC_CALLER_CLEANUP   = 1 << 4    # caller cleans up the stack
