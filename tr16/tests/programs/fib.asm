; expect: r1=55 r2=89 r3=0
        li   r1 0          ; a = F(0)
        li   r2 1          ; b = F(1)
        li   r3 10         ; iterations
loop:   cmp  r3 r0
        beq  done
        add  r4 r1 r2
        mov  r1 r2
        mov  r2 r4
        dec  r3
        b    loop
done:   hlt
