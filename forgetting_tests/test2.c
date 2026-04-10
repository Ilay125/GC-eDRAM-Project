#include <stdint.h>
#include <gem5/m5ops.h>

/** 
 * Retention reuse instead eviction
 * Check done with 4KiB cache and drt=10
 */
#define STRIDE 1024   // ints = 4 KiB stride
#define LINES 6

__attribute__((aligned(64))) static volatile int arr[STRIDE * LINES];
__attribute__((aligned(64))) static volatile int sink = 0;

int main(void) {
    // Fill 4 congruent lines into the same set
    arr[0 * STRIDE] = 0;
    arr[1 * STRIDE] = 1;
    arr[2 * STRIDE] = 2;
    arr[3 * STRIDE] = 3;

    sink += arr[0 * STRIDE];
    sink += arr[1 * STRIDE];
    sink += arr[2 * STRIDE];
    sink += arr[3 * STRIDE];

    // Wait so at least the oldest one can expire
    for (uint64_t i = 0; i < 10000ULL; ++i) {
        asm volatile("nop");
    }

    m5_reset_stats(0, 0);

    // 5th congruent line, should trigger victim selection
    arr[4 * STRIDE] = 4;
    sink += arr[4 * STRIDE];

    m5_dump_stats(0, 0);
    m5_exit(0);

    while (1) {
        asm volatile("nop");
    }
}