; expect: r3=0 flags=5
        fli  r1 1
        fli  r2 2
        subf r3 r1 r2       ; no sign bit: negative result -> 0, V set (Z from zero result)
        hlt
