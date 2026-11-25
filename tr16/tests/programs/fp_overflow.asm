; expect: r3=0 flags=5
        fli  r1 31.5        ; largest value
        fli  r2 1
        addf r3 r1 r2
        hlt
