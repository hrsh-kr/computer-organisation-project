; expect: r2=0 r4=0 flags=6
        li   r1 -1
        shli r2 r1 15       ; 0xFFFF << 15 = 0x8000
        shli r2 r2 1        ; 0x8000 << 1 = 0, last bit shifted out was 1
        li   r3 1
        shri r4 r3 1        ; 1 >> 1 = 0, bit shifted out was 1: C and Z set
        hlt
