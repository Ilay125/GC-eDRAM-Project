#include <stdint.h>
#include <gem5/m5ops.h>

/** 
 * Retention miss
 * Test done with 16KiB cache and varying drt
 */
#define SIZE 16

__attribute__((aligned(64))) static volatile int arr[SIZE];
__attribute__((aligned(64))) static volatile int sink = 0;

int main(void) {
    arr[0] = 42;
    sink += arr[0];
    sink += arr[0];

    for (uint64_t i = 0; i < 200000ULL; ++i) {
        asm volatile("nop");
    }

    m5_reset_stats(0, 0);

    sink += arr[0];

    m5_dump_stats(0, 0);
    m5_exit(0);

    while (1) {
        asm volatile("nop");
    }
}