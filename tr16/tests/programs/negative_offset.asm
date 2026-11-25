; expect: r3=9 mem[50]=9
        li   r1 52
        li   r2 9
        st   r2 [r1-2]
        ld   r3 [r1 - 2]
        hlt
