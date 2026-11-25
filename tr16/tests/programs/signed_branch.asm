; expect: r3=1 r1=65533
        li   r1 -3
        li   r2 2
        cmp  r1 r2          ; -3 < 2 (signed)
        blt  less
        li   r3 0
        hlt
less:   li   r3 1
        hlt
