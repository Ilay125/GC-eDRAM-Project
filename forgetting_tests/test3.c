#include <stdint.h>
#include <stdio.h>
#include <gem5/m5ops.h>

#define STRIDE 1024
#define LINES 6

__attribute__((aligned(64))) static volatile int arr[STRIDE * LINES];

int main(void) {
    int x;

    arr[0 * STRIDE] = 0;
    
    arr[1 * STRIDE] = 1;
    arr[2 * STRIDE] = 2;
    arr[3 * STRIDE] = 3;
    arr[4 * STRIDE] = 4;

    arr[0] = 1;

    for (uint64_t i = 0; i < 200000ULL; ++i) {
        asm volatile("nop");
    }

    m5_reset_stats(0, 0);

    x = arr[0];   // the only access we care about

    m5_dump_stats(0, 0);

    printf("x=%d\n", x);
    fflush(stdout);

    m5_exit(0);

    while (1) {
        asm volatile("nop");
    }
}