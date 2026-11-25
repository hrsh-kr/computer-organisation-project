; expect: r3=0 flags=5
        li   r1 10
        div  r3 r1 r0       ; result 0, V set (Z set from zero result)
        hlt
