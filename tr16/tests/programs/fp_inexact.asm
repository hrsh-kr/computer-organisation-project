; expect: r3=96 flags=2
        fli  r1 1
        fli  r2 0.0078125   ; 1/128, smallest nonzero value
        addf r3 r1 r2       ; 1.0078125 rounds to 1.0, C flags "inexact"
        hlt
