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

    if not keep_asm:
        os.remove(asm_file)
    os.remove(obj_file)

    print(f"Generated executable: {output_name}", flush=True)
    return True


def run_executable(binary_path):
    print(f"Running {binary_path} ...", flush=True)
    completed = subprocess.run([os.path.abspath(binary_path)], check=False)
    return completed.returncode


def parse_args(argv):
    parser = argparse.ArgumentParser(description="Compile toy language to x86_64 Linux executable.")
    parser.add_argument("source", nargs="?", help="Path to source file")

    run_group = parser.add_mutually_exclusive_group()
    run_group.add_argument("--run", dest="run", action="store_true", help="Run executable after successful build")
    run_group.add_argument("--no-run", dest="run", action="store_false", help="Only compile/build; do not run")
    parser.set_defaults(run=None)

    parser.add_argument("--output", default="output", help="Output executable name (default: output)")
    parser.add_argument("--keep-asm", action="store_true", help="Keep output.asm after successful build")
    return parser.parse_args(argv)


def should_auto_run(run_flag):
    if run_flag is not None:
        return run_flag
    return sys.stdin.isatty() and sys.stdout.isatty()


def main(argv=None):
    args = parse_args(argv or sys.argv[1:])
    source_path = args.source if args.source else input("File> ").strip()

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    asm_code = compile_source(source_path)
    built = build_executable(asm_code, output_name=args.output, keep_asm=args.keep_asm)

    run_after_build = should_auto_run(args.run)
    if run_after_build:
        if not built:
            print("Cannot run: executable was not built.", flush=True)
            return 1
        return run_executable(args.output)

    if built:
        print("Tip: use --run to execute immediately.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
