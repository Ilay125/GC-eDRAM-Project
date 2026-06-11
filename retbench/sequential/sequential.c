/**
 * The purpose of the test is to isolate the effect of retention in between readings of active blocks.
 * All misses here will be retention or compulsory.
 * This should simulate the degredation in tests like SHA.
 */

#include "sequential.h"
#include <stdio.h>
#include <stdlib.h>

unsigned char alu_delay(int iters) {
    for (register int i=0; i < iters; i++) {
        __asm__ volatile ("nop");
    }

    return 0;
}


int main(int argc, char** argv) {
    if (argc < 2) {
        fprintf(stderr, "Delay is not defined.");
        return 1;
    }
    
    int delay = atoi(argv[1]);
    static unsigned x;

    for (int j = 0; j < len; j++) {
        x += a[i];
        x += alu_delay(delay);
    }

    printf("%u\n", (x&0xFF)); // to prevent opt
    return 0;
}