/**
 * The purpose of the test is to find the read/write ratio needed for improving
 */

#include "mixed.h"
#include <stdio.h>
#include <stdlib.h>

#define ITER 10

unsigned char alu_delay(unsigned char x, int iters) {
    unsigned data = x;

    for (int i = 0; i < iters; i++) {
        data = (data * 2) + i;
        data = data & 0xFF;
    }

    return data & 0xFF;
}


int main(int argc, char** argv) {
    if (argc < 3) {
        fprintf(stderr, "Delay or stride are not defined.");
        return 1;
    }
    
    int delay = atoi(argv[1]);
    int stride = atoi(argv[2]);
    if (stride == 0) {
        fprintf(stderr, "Stride should be positive.");
        return 1;
    }

    static unsigned x;

    for (int j = 0; j < ITER; j++) {
        for (int i = 0; i < len; i++) {
            if (i % stride == 0) { // perform write
                arr[i] = (j + x) & 0xFF;

            }
             
            // reads every time
            x += arr[i];
            x = x & 0xFF;
        }

        x = alu_delay(x, delay);
    }

    printf("%u\n", (x&0xFF)); // to prevent opt
    return 0;
}