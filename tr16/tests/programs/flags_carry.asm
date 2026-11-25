; expect: r2=0 flags=6
        li   r1 -1
        addi r2 r1 1        ; 0xFFFF + 1 -> 0, carry out, zero
        hlt
