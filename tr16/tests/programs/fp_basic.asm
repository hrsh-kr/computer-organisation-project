; expect: r1=112 r2=132 r3=156 flags=0
        fli  r1 1.5         ; exp 3, mantissa 16 -> 0b01110000
        fli  r2 2.25
        addf r3 r1 r2       ; 3.75 = exp 4, mantissa 28 -> 0b10011100
        hlt
