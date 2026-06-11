import random
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--size", type=int, default=14, help="Size of array (2^size)")
args = parser.parse_args()

size = 2 ** (args.size)

buff = []
for i in range(size):
    buff.append(f"{random.randint(0, 255)}")

buff_str = ", ".join(buff)

with open(f"./deadblk.h", "w") as file:
    file.write("#ifndef __DEADBLK__\n#define __DEADBLK__\n\n")

    file.write(f"__attribute__((aligned(64))) unsigned char buff[{len(buff)}] = "+"{"+buff_str+"};\n\n")

    file.write(f"unsigned len_a = {len(buff) // 2};\n")
    file.write("unsigned char* a = &(buff[0]);\n")

    file.write(f"\nunsigned len_b = {len(buff) // 2};\n")
    file.write(f"unsigned char* b = &(buff[{len(buff) // 2}]);\n")

    file.write("\n\n#endif\t// __DEADBLK__")

print(f"Generated deadblk.h file")