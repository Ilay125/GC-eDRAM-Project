CC ?= gcc
CFLAGS ?= -O2 -Wall

.PHONY: all clean seq temp dead wb mixed

all: seq temp dead wb mixed

clean:
	find . -type f \( -name '*.exe' -o -name '*.o' \) -delete

seq:
	$(CC) $(CFLAGS) sequential/sequential.c -o sequential/sequential.exe

temp:
	$(CC) $(CFLAGS) temporal/temporal.c -o temporal/temporal.exe

dead:
	$(CC) $(CFLAGS) deadblk/deadblk.c -o deadblk/deadblk.exe

wb:
	$(CC) $(CFLAGS) writebacks/writebacks.c -o writebacks/writebacks.exe

mixed:
	$(CC) $(CFLAGS) mixed/mixed.c -o mixed/mixed.exe