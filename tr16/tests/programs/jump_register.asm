; expect: r1=7 r2=0
        li   r3 target
        jr   r3
        li   r1 99          ; skipped
        hlt
target: li   r1 7
        hlt
