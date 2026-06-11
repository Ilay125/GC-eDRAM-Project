/**
 * The purpose of the test is to isolate the effect replacing dead blocks without the need to evict.
 * Filling the cache with arrA, forgetting it because of computations and then reading arrB.
 * Each array is 0.25 of cache size to keep space for system vars.
 * Simulates a bunch of addresses that are not one after the other.
 */

#include "deadblk.h"
#include <stdio.h>
#include <stdlib.h>

#define ITER 1000

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
    unsigned x = 0;

    for (int j = 0; j < ITER; j++) {
        // filling with arr "a"
        for (int i = 0; i < len_a; i++) {
            x += a[i];
            x = x & 0xFF; // prevent overflow
        }

        x += alu_delay(delay);

        // filling with arr "b"
        for (int i = 0; i < len_b; i++) {
            x += b[i];
            x = x & 0xFF; // prevent overflow
        }
        x += alu_delay(delay);
    }

    printf("%u\n", (x&0xFF)); // to prevent opt
    return 0;
}