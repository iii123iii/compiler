from lexer import Lexer
from parser import Parser
import argparse
import os
import shutil
import subprocess
import sys


def compile_source(source_path):
    parser = Parser()

    with open(source_path, "r", encoding="utf-8") as file:
        for line_no, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            tokens = Lexer(line).lexer()
            parser.parse(tokens, line_no)

    return parser.finish()


def build_executable(asm_code, output_name="output", keep_asm=False):
    asm_file = "output.asm"
    obj_file = "output.o"

    with open(asm_file, "w", encoding="utf-8") as f:
        f.write(asm_code)

    if shutil.which("nasm") is None or shutil.which("ld") is None:
        print("Warning: nasm and/or ld not found. Generated output.asm only.", flush=True)
        return False

    subprocess.run(["nasm", "-f", "elf64", asm_file, "-o", obj_file], check=True)
    subprocess.run(["ld", obj_file, "-o", output_name], check=True)

    os.remove(asm_file)
    os.remove(obj_file)
    print(f"Generated executable: {output_name}")
    return True


def main():
    source_path = sys.argv[1] if len(sys.argv) > 1 else input("File> ").strip()
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    asm_code = compile_source(source_path)
    build_executable(asm_code)


if __name__ == "__main__":
    main()
