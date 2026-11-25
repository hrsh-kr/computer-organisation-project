; expect: r1=6 r2=0
        li   r1 48
        li   r2 18
loop:   cmp  r2 r0
        beq  done
        mod  r3 r1 r2
        mov  r1 r2
        mov  r2 r3
        b    loop
done:   hlt
