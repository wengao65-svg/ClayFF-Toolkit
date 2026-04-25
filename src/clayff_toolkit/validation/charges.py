from __future__ import annotations

from pathlib import Path
from typing import Iterable


def parse_atoms_section_charges(path: str | Path) -> list[float]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    atoms_start = -1
    for index, line in enumerate(lines):
        if line.startswith("Atoms"):
            atoms_start = index + 2
            break

    if atoms_start == -1:
        raise ValueError(f"Atoms section not found in: {path}")

    charges: list[float] = []
    line_index = atoms_start
    while line_index < len(lines):
        line = lines[line_index].strip()
        if not line:
            if line_index > atoms_start:
                break
            line_index += 1
            continue

        parts = line.split()
        if len(parts) < 7:
            break
        try:
            charges.append(float(parts[3]))
        except ValueError:
            break
        line_index += 1
    return charges


def calculate_net_charge(path: str | Path) -> float:
    return sum(parse_atoms_section_charges(path))


def iter_data_files(directory: str | Path) -> Iterable[Path]:
    root = Path(directory)
    return sorted(root.glob("MMT_*/*.data"))


def check_charges(directory: str | Path = ".") -> list[tuple[Path, float]]:
    data_files = list(iter_data_files(directory))
    results: list[tuple[Path, float]] = []
    if not data_files:
        print("未找到符合 MMT_*/*.data 的文件，请确认是否在正确的目录下运行！")
        return results

    print(f"找到 {len(data_files)} 个 LAMMPS data 文件，开始批量核对净电荷...\n")
    print("=" * 60)

    for path in data_files:
        net_charge = calculate_net_charge(path)
        results.append((path, net_charge))
        print(f"文件路径 : {path}")
        print(f"净电荷   : {net_charge:.6f} e")
        if abs(net_charge) > 1e-5:
            print("状态     : [警告] 体系不严格满足电中性！")
        else:
            print("状态     : [完美] 体系电中性。")
        print("-" * 60)
    return results


if __name__ == "__main__":
    check_charges()
