#!/usr/bin/env python3

"""
Read Quantum ESPRESSO projwfc.x text output and prepare
orbital-resolved fat-band data for Mo d orbitals.

Designed for scalar-relativistic / non-SOC calculations.

Output columns:

1   k-distance
2   energy - Eref
3   Mo dz2
4   Mo dxz
5   Mo dyz
6   Mo dx2-y2
7   Mo dxy
8   Mo e'  = dx2-y2 + dxy
9   Mo e'' = dxz + dyz
10  Mo d total
"""

import argparse
import math
import re
import sys
from collections import defaultdict


# ------------------------------------------------------------
# Regular expressions
# ------------------------------------------------------------

# Example:
# state #   5: atom   1 (Mo ), wfc  3 (l=2 m=1)
STATE_RE = re.compile(
    r"state\s*#\s*(\d+).*?"
    r"atom\s+(\d+)\s+\(\s*([A-Za-z]+)\s*\).*?"
    r"l\s*=\s*(\d+).*?"
    r"m\s*=\s*(\d+)"
)

# Example:
# k = 0.0000000000 0.0000000000 0.0000000000
K_RE = re.compile(
    r"^\s*k\s*=\s*"
    r"([-+0-9.EeDd]+)\s+"
    r"([-+0-9.EeDd]+)\s+"
    r"([-+0-9.EeDd]+)"
)

# Example:
# ==== e(   4) =    -1.23456 eV ====
E_RE = re.compile(
    r"e\(\s*(\d+)\s*\)\s*=\s*([-+0-9.EeDd]+)\s*eV",
    re.IGNORECASE
)

# Example:
# 0.523*[#  5]
WEIGHT_RE = re.compile(
    r"([-+0-9.EeDd]+)\s*\*\s*\[\s*#\s*(\d+)\s*\]"
)


def ffloat(value):
    """Convert Fortran D exponent to Python float."""
    return float(value.replace("D", "E").replace("d", "e"))


def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Prepare Mo-d fat bands from QE projwfc.x output"
    )

    parser.add_argument(
        "input",
        help="projwfc.x output file, e.g. projwfc.out"
    )

    parser.add_argument(
        "-o",
        "--output",
        default="fatbands.dat",
        help="output file name (default: fatbands.dat)"
    )

    parser.add_argument(
        "--eref",
        type=float,
        default=0.0,
        help="reference energy in eV to subtract, usually EF or VBM"
    )

    parser.add_argument(
        "--element",
        default="Mo",
        help="element to project onto (default: Mo)"
    )

    return parser.parse_args()


def parse_projwfc(filename, element):
    """
    Parse:
      1. atomic-state definitions
      2. k points
      3. band energies
      4. projection weights
    """

    with open(filename, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    # --------------------------------------------------------
    # Find Mo d states
    # --------------------------------------------------------

    orbital_states = defaultdict(list)

    orbital_map = {
        1: "dz2",
        2: "dxz",
        3: "dyz",
        4: "dx2y2",
        5: "dxy",
    }

    for line in lines:
        match = STATE_RE.search(line)

        if match:
            state_number = int(match.group(1))
            atom_number = int(match.group(2))
            symbol = match.group(3)
            l_value = int(match.group(4))
            m_value = int(match.group(5))

            if symbol.lower() == element.lower() and l_value == 2:
                if m_value in orbital_map:
                    orbital = orbital_map[m_value]
                    orbital_states[orbital].append(state_number)

                    print(
                        f"Found {element} d state: "
                        f"state={state_number:4d}, "
                        f"atom={atom_number:3d}, "
                        f"orbital={orbital}"
                    )

    required = ["dz2", "dxz", "dyz", "dx2y2", "dxy"]

    missing = [
        orb for orb in required
        if len(orbital_states[orb]) == 0
    ]

    if missing:
        print(
            "\nERROR: Could not find the following orbitals:",
            ", ".join(missing),
            file=sys.stderr
        )

        print(
            "This script assumes a non-SOC projwfc.x output "
            "with l and m quantum numbers.",
            file=sys.stderr
        )

        sys.exit(1)

    # Reverse lookup:
    # state number -> orbital label
    state_to_orbital = {}

    for orbital, states in orbital_states.items():
        for state in states:
            state_to_orbital[state] = orbital

    # --------------------------------------------------------
    # Parse bands
    # --------------------------------------------------------

    records = []

    current_k = None
    current_ik = -1
    current_band = None
    current_energy = None
    psi_buffer = []

    kpoints = []

    def flush_state():
        """
        Convert accumulated psi projection line(s)
        into orbital weights.
        """

        nonlocal current_band
        nonlocal current_energy
        nonlocal psi_buffer

        if (
            current_k is None
            or current_band is None
            or current_energy is None
        ):
            psi_buffer = []
            return

        text = " ".join(psi_buffer)

        weights = {
            "dz2": 0.0,
            "dxz": 0.0,
            "dyz": 0.0,
            "dx2y2": 0.0,
            "dxy": 0.0,
        }

        for value, state_text in WEIGHT_RE.findall(text):
            state_number = int(state_text)
            weight = ffloat(value)

            orbital = state_to_orbital.get(state_number)

            if orbital is not None:
                weights[orbital] += weight

        records.append({
            "ik": current_ik,
            "k": current_k,
            "band": current_band,
            "energy": current_energy,
            **weights,
        })

        psi_buffer = []

    for line in lines:

        # New k point
        kmatch = K_RE.search(line)

        if kmatch:
            flush_state()

            current_k = (
                ffloat(kmatch.group(1)),
                ffloat(kmatch.group(2)),
                ffloat(kmatch.group(3)),
            )

            kpoints.append(current_k)
            current_ik += 1

            current_band = None
            current_energy = None

            continue

        # New band energy
        ematch = E_RE.search(line)

        if ematch:
            flush_state()

            current_band = int(ematch.group(1))
            current_energy = ffloat(ematch.group(2))
            psi_buffer = []

            continue

        # Projection lines
        if current_band is not None:

            if "psi =" in line or psi_buffer:
                psi_buffer.append(line.strip())

                # QE terminates a projection block with |psi|^2
                if "|psi|^2" in line:
                    flush_state()

    flush_state()

    return records, kpoints


def cumulative_k_distance(kpoints):
    """Construct cumulative distance along the k path."""

    if not kpoints:
        return []

    distance = [0.0]

    for i in range(1, len(kpoints)):
        dk = math.sqrt(
            (kpoints[i][0] - kpoints[i - 1][0]) ** 2
            + (kpoints[i][1] - kpoints[i - 1][1]) ** 2
            + (kpoints[i][2] - kpoints[i - 1][2]) ** 2
        )

        distance.append(distance[-1] + dk)

    return distance


def write_output(records, kpoints, output, eref):
    kdist = cumulative_k_distance(kpoints)

    bands = sorted(set(record["band"] for record in records))

    with open(output, "w", encoding="utf-8") as f:

        f.write(
            "# 1:kdist 2:E-Eref 3:dz2 4:dxz 5:dyz "
            "6:dx2-y2 7:dxy 8:eprime 9:edoubleprime "
            "10:d_total\n"
        )

        for band in bands:

            band_records = [
                r for r in records
                if r["band"] == band
            ]

            band_records.sort(key=lambda r: r["ik"])

            for r in band_records:

                x = kdist[r["ik"]]
                energy = r["energy"] - eref

                dz2 = r["dz2"]
                dxz = r["dxz"]
                dyz = r["dyz"]
                dx2y2 = r["dx2y2"]
                dxy = r["dxy"]

                eprime = dx2y2 + dxy
                edoubleprime = dxz + dyz

                dtotal = (
                    dz2
                    + dxz
                    + dyz
                    + dx2y2
                    + dxy
                )

                f.write(
                    f"{x:16.8f} "
                    f"{energy:16.8f} "
                    f"{dz2:12.8f} "
                    f"{dxz:12.8f} "
                    f"{dyz:12.8f} "
                    f"{dx2y2:12.8f} "
                    f"{dxy:12.8f} "
                    f"{eprime:12.8f} "
                    f"{edoubleprime:12.8f} "
                    f"{dtotal:12.8f}\n"
                )

            # blank lines separate bands for gnuplot
            f.write("\n\n")

    print(f"\nWritten: {output}")
    print(f"Number of k points: {len(kpoints)}")
    print(f"Number of bands: {len(bands)}")


def main():
    args = parse_arguments()

    records, kpoints = parse_projwfc(
        args.input,
        args.element
    )

    if not records:
        print(
            "ERROR: No band projections were parsed.",
            file=sys.stderr
        )
        sys.exit(1)

    write_output(
        records,
        kpoints,
        args.output,
        args.eref
    )


if __name__ == "__main__":
    main()
    
    