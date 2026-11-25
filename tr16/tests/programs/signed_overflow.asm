; expect: r3=32768 flags=9
        li   r1 1
        shli r1 r1 14       ; 0x4000
        add  r3 r1 r1       ; 0x8000: N set, signed overflow V set, no carry
        hlt
