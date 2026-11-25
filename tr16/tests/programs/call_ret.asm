; expect: r1=36 r7=2
        li   r1 6
        call square
        hlt
square: mul  r1 r1 r1
        ret
