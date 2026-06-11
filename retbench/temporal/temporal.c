/**
 * The purpose of the test is to isolate the effect of retention after reading an active block.
 * All misses here will be retention because workload size is <= L1 size.
 * This should simulate the degredation in tests like dijkstra.
 */

#include "temporal.h"
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
    static unsigned x;

    for (int i = 0; i < ITER; i++) {
        for (int j = 0; j < len; j++) {
            x += arr[j];
            x = x & 0xFF; // prevent overflow
        }

        alu_delay(delay);
    }

    printf("%u\n", (x&0xFF)); // to prevent opt
    return 0;
}