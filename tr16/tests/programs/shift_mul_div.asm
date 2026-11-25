; expect: r0=0 r2=48 r3=12 r5=336 r6=48
        li   r1 3
        shli r2 r1 4        ; 48
        shri r3 r2 2        ; 12
        li   r4 7
        mul  r5 r2 r4       ; 336
        div  r6 r5 r4       ; 48
        add  r0 r1 r1       ; writes to r0 are ignored
        hlt
