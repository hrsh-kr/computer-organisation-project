; expect: r3=7 mem[103]=7
        li   r1 100
        li   r2 7
        st   r2 [r1+3]
        ld   r3 [r1 + 3]
        hlt
