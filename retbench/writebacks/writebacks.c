/**
 * The purpose of the test is to isolate the effect of retention after marking a lot of blocks as dirty.
 * The point is to charactarize the WB spamming.
 */

#include "writebacks.h"
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
    static unsigned x = 0;

    for (int i = 0; i < ITER; i++) {
        // Write to the entire array
        for (int j = 0; j < len; j++) {
            arr[j] = i + x;
            x += arr[j]; // prevent opt
            x = x & 0xFF; // prevent overflow
        }

        // wait
        x = alu_delay(delay);
    }

    printf("%u\n", (x&0xFF)); // to prevent opt
    return 0;
}