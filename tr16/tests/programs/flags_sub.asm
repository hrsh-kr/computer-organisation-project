; expect: r3=65534 flags=8
        li   r1 5
        li   r2 7
        sub  r3 r1 r2       ; wraps: N set, borrow so C clear
        hlt
