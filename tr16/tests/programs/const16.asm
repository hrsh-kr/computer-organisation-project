; expect: r1=4660 r2=65535
        li   r1 0x34
        lhi  r1 0x12        ; r1 = 0x1234
        li   r2 -1          ; sign-extended: 0xFFFF
        hlt
