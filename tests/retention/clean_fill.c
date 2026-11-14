/*
 * Directed SRC test for clean deadline drops: read every line of a 48 KiB
 * L1D once (every k-th line is stored instead, if k > 0), then spin on
 * registers. The untouched clean lines are dropped at their deadline.
 * 12 pages: a 4 KiB page covers each of the 64 sets once.
 *
 *   clean_fill <spin iterations> [k]
 *
 * Exits 0 if the stored lines still hold the value stored.
 */
#include <stdlib.h>

#define BYTES (48 * 1024)
#define LINE 64

static volatile char buf[BYTES] __attribute__((aligned(4096)));

int
main(int argc, char **argv)
{
    long n = argc > 1 ? atol(argv[1]) : 1000000;
    long k = argc > 2 ? atol(argv[2]) : 0;
    char sum = 0;

    for (long i = 0; i < BYTES; i += LINE) {
        if (k > 0 && (i / LINE) % k == 0) {
            buf[i] = (char)(i / LINE + 1);
        } else {
            sum += buf[i];
        }
    }

    unsigned long x = 1;
    for (long i = 0; i < n; i++) {
        x = x * 6364136223846793005UL + 1442695040888963407UL;
    }
    __asm__ volatile("" : : "r"(x), "r"(sum));

    for (long i = 0; i < BYTES; i += LINE) {
        if (k > 0 && (i / LINE) % k == 0 && buf[i] != (char)(i / LINE + 1)) {
            return 1;
        }
    }
    return 0;
}
