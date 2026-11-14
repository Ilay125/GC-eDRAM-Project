/*
 * Directed SRC retention test: store to word 0 of one cache line in a
 * loop, so the line stays dirty and is never refilled. Without a refresh
 * the line expires DRT after its fill.
 *
 *   store_loop <iterations>
 *
 * Exits 0 if the final value is the last one stored.
 */
#include <stdlib.h>

static volatile long line[8] __attribute__((aligned(64)));

int
main(int argc, char **argv)
{
    long n = argc > 1 ? atol(argv[1]) : 1000000;

    for (long i = 0; i < n; i++) {
        line[0] = i;
    }

    return line[0] == n - 1 ? 0 : 1;
}
