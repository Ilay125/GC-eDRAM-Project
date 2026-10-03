/*
 * Directed SRC test for the refresh daemon's worst case: dirty every line
 * of a 48 KiB L1D, then spin on registers while the daemon keeps them
 * alive. 12 pages: a 4 KiB page covers each of the 64 sets once, so
 * every set gets 12 dirty lines, whatever the physical page mapping.
 *
 *   dirty_fill <spin iterations>
 *
 * Exits 0 if every line still holds the value stored.
 */
#include <stdlib.h>

#define BYTES (48 * 1024)
#define LINE 64

static volatile char buf[BYTES] __attribute__((aligned(4096)));

int
main(int argc, char **argv)
{
    long n = argc > 1 ? atol(argv[1]) : 1000000;

    for (long i = 0; i < BYTES; i += LINE) {
        buf[i] = (char)(i / LINE + 1);
    }

    unsigned long x = 1;
    for (long i = 0; i < n; i++) {
        x = x * 6364136223846793005UL + 1442695040888963407UL;
    }
    __asm__ volatile("" : : "r"(x));

    for (long i = 0; i < BYTES; i += LINE) {
        if (buf[i] != (char)(i / LINE + 1)) {
            return 1;
        }
    }
    return 0;
}
