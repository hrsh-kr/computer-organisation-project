; expect: flags=6
        li   r1 9
        cmp  r1 r1          ; Z set, C set (no borrow)
        hlt
