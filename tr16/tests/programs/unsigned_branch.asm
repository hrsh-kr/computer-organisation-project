; expect: r3=1 r4=0
        li   r1 1
        li   r2 -1          ; 0xFFFF: huge unsigned, -1 signed
        cmp  r1 r2
        blo  below          ; 1 < 65535 unsigned -> taken
        hlt
below:  li   r3 1
        cmp  r2 r1
        bge  signed_ok      ; -1 >= 1 is false signed -> not taken
        hlt
signed_ok: li   r4 5
        hlt
