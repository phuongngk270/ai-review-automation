import sys


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: python -m automation <command>", file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "smoke":
        from automation.anduin_client import smoke
        return smoke()
    print(f"unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
