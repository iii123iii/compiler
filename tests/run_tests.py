import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "tests" / "cases"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_case(src: Path) -> tuple[bool, str]:
    stdin_path = src.with_suffix(".stdin")
    out_path = src.with_suffix(".out")
    code_path = src.with_suffix(".code")
    mode_path = src.with_suffix(".mode")

    stdin_data = read_text(stdin_path) if stdin_path.exists() else ""
    mode = read_text(mode_path).strip() if mode_path.exists() else "run"

    compile_proc = subprocess.run(
        [sys.executable, "main.py", str(src)],
        cwd=ROOT,
        input=stdin_data,
        capture_output=True,
        text=True,
        check=False,
    )

    if compile_proc.returncode != 0:
        return False, f"compile failed for {src.name}:\n{compile_proc.stderr}{compile_proc.stdout}"

    bin_path = ROOT / "output"
    asm_path = ROOT / "output.asm"

    if mode == "compile_only":
        produced = bin_path.exists() or asm_path.exists()
        if not produced:
            return False, f"compile-only case produced neither output nor output.asm for {src.name}"
        if bin_path.exists():
            bin_path.unlink()
        if asm_path.exists():
            asm_path.unlink()
        return True, f"{src.name} compile-only passed"

    expected_out = read_text(out_path)
    expected_code = int(read_text(code_path).strip())

    if not bin_path.exists():
        return False, f"no executable produced for {src.name}; asm exists={asm_path.exists()}"

    run_proc = subprocess.run(
        [str(bin_path)],
        cwd=ROOT,
        input=stdin_data,
        capture_output=True,
        text=True,
        check=False,
    )

    bin_path.unlink(missing_ok=True)
    if asm_path.exists():
        asm_path.unlink()

    actual_out = run_proc.stdout
    actual_code = run_proc.returncode

    if actual_out != expected_out:
        return (
            False,
            f"output mismatch for {src.name}: expected={expected_out!r} actual={actual_out!r}",
        )

    if actual_code != expected_code:
        return (
            False,
            f"exit code mismatch for {src.name}: expected={expected_code} actual={actual_code}",
        )

    return True, f"{src.name} passed"


def main() -> int:
    cases = sorted(CASES.glob("*.src"))
    if not cases:
        print("No test cases found.")
        return 1

    failed = []
    for case in cases:
        ok, message = run_case(case)
        print(message)
        if not ok:
            failed.append(case.name)

    if failed:
        print(f"\nFailed cases: {', '.join(failed)}")
        return 1

    print("\nAll compiler tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
