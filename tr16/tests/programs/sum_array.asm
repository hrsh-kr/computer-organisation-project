; expect: r1=60 mem[total]=60 mem[arr]=5
        li   r2 arr
        li   r3 4          ; element count
        li   r1 0
loop:   ld   r4 [r2]
        add  r1 r1 r4
        addi r2 r2 1
        dec  r3
        cmp  r3 r0
        bne  loop
        li   r5 total
        st   r1 [r5]
        hlt
.word arr 5 10 20 25
.word total
