import random
import argparse

parser = argparse.ArgumentParser()

parser.add_argument("--size", type=int, default=14, help="Size of array (2^size)")
parser.add_argument("--name", type=str, help="Name of the file")
args = parser.parse_args()

size = 2 ** (args.size)
name = args.name

arr = []
for i in range(size):
    arr.append(f"{random.randint(0, 255)}")

arr_str = ", ".join(arr)

with open(f"{name}/{name}.h", "w") as file:
    file.write(f"#ifndef __{name.upper()}__\n#define __{name.upper()}__\n\n")

    file.write(f"unsigned len = {len(arr)};\n")
    file.write("unsigned char arr[] = {" + arr_str + "};\n")

    file.write(f"\n\n#endif\t// __{name.upper()}__")

print(f"Generated {name}.h file")