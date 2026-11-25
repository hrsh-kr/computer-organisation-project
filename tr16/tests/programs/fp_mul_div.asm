; expect: r3=150 r4=132 flags=0
        fli  r1 1.5
        fli  r2 2.25
        mulf r3 r1 r2       ; 3.375, exactly representable
        divf r4 r3 r1       ; back to 2.25
        hlt
