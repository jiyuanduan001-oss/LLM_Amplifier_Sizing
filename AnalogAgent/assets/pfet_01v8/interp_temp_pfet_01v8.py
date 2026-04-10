"""
Temperature interpolation for sky130 pfet_01v8 gm/ID LUT.

Linear interpolation between reference temperatures:
  - T in [0, 25]: interpolate between 0C and 25C
  - T in [25, 75]: interpolate between 25C and 75C

Usage: modify target_temp below, then run the script.
Output: raw LUT + processed LUT at the target temperature.
"""

import numpy as np
import os
import glob
from pathlib import Path

# === Configuration ===
base_path = str(Path(__file__).resolve().parent)

device = "pfet_01v8"
W = 2e-6

# Target temperature (C)
target_temp = 40

# Corners to process (all or subset)
corners = ["tt", "fs", "sf", "ff", "ss"]

# === Determine reference temperatures ===
if target_temp <= 25:
    T_lo, T_hi = 0, 25
elif target_temp <= 75:
    T_lo, T_hi = 25, 75
else:
    print(f"ERROR: target_temp={target_temp}C is outside [0, 75] range")
    exit(1)

# Interpolation weight: alpha=0 -> T_lo, alpha=1 -> T_hi
alpha = (target_temp - T_lo) / (T_hi - T_lo)
print(f"Target: {target_temp}C, interpolating between {T_lo}C and {T_hi}C (alpha={alpha:.4f})")

for corner in corners:
    path_lo = os.path.join(base_path, corner, f"{T_lo}C", "initial")
    path_hi = os.path.join(base_path, corner, f"{T_hi}C", "initial")

    # Output directories
    raw_outdir = os.path.join(base_path, corner, f"{target_temp}C", "initial")
    proc_outdir = os.path.join(base_path, corner, f"{target_temp}C", "processed")
    os.makedirs(raw_outdir, exist_ok=True)
    os.makedirs(proc_outdir, exist_ok=True)

    files_lo = sorted(glob.glob(os.path.join(path_lo, f"gmid_{device}_L*n.txt")),
                      key=lambda f: int(os.path.basename(f).split("_L")[1].split("n.txt")[0]))

    count = 0
    for file_lo in files_lo:
        basename = os.path.basename(file_lo)
        L_nm = int(basename.split("_L")[1].split("n.txt")[0])
        L_um = L_nm / 1000.0

        file_hi = os.path.join(path_hi, basename)  # path_hi already points to initial/
        if not os.path.exists(file_hi):
            print(f"  WARNING: {file_hi} not found, skipping")
            continue

        # Load raw data (skip comment lines)
        # Columns: vgs vth gm id gds cgg cgs cgd
        data_lo = []
        data_hi = []

        for fpath, storage in [(file_lo, data_lo), (file_hi, data_hi)]:
            with open(fpath, 'r') as f:
                for line in f:
                    if line.startswith('#'):
                        continue
                    try:
                        vals = list(map(float, line.strip().split()))
                        if len(vals) >= 8:
                            storage.append(vals[:8])
                    except (ValueError, IndexError):
                        continue

        data_lo = np.array(data_lo)
        data_hi = np.array(data_hi)

        # Both files should have same number of rows (same VGS sweep)
        n_rows = min(len(data_lo), len(data_hi))
        data_lo = data_lo[:n_rows]
        data_hi = data_hi[:n_rows]

        # Linear interpolation: data = (1-alpha)*data_lo + alpha*data_hi
        data_interp = (1 - alpha) * data_lo + alpha * data_hi

        # VGS should stay the same (both sweeps use same VGS)
        data_interp[:, 0] = data_lo[:, 0]

        # === Write raw LUT ===
        raw_file = os.path.join(raw_outdir, basename)
        with open(raw_file, 'w') as f:
            f.write(f"# sky130 {device} gm/ID Lookup Table (interpolated)\n")
            f.write(f"# Corner: {corner}\n")
            f.write(f"# Temperature: {target_temp} C (interpolated from {T_lo}C and {T_hi}C)\n")
            f.write(f"# W = {W*1e6:.1f} um\n")
            f.write(f"# L = {L_um:.4g} um ({L_nm} nm)\n")
            f.write(f"# VDS = -0.6 V  (VSD = 0.6 V)\n")
            f.write(f"# Columns: vgs [V]  vth [V]  gm [S]  id [A]  gds [S]  cgg [F]  cgs [F]  cgd [F]\n")
            f.write(f"#{'vgs':>14s}{'vth':>16s}{'gm':>16s}{'id':>16s}{'gds':>16s}{'cgg':>16s}{'cgs':>16s}{'cgd':>16s}\n")
            for row in data_interp:
                f.write("".join(f"{v:16.6e}" for v in row) + "\n")

        # === Compute and write processed LUT ===
        proc_file = os.path.join(proc_outdir, basename)
        with open(proc_file, 'w') as f:
            f.write(f"# sky130 {device} gm/ID Processed Lookup Table (interpolated)\n")
            f.write(f"# Corner: {corner}\n")
            f.write(f"# Temperature: {target_temp} C (interpolated from {T_lo}C and {T_hi}C)\n")
            f.write(f"# W = {W*1e6:.1f} um\n")
            f.write(f"# L = {L_um:.4g} um ({L_nm} nm)\n")
            f.write(f"# Columns: gm/id [1/V]  gm/gds [V/V]  id/W [A/m]  ft [Hz]  Cgg/W [F/m]  Cgd/W [F/m]  Cgs/W [F/m]  Vov [V]\n")
            f.write(f"#{'gm/id':>14s}{'gm/gds':>16s}{'id/W':>16s}{'ft':>16s}{'Cgg/W':>16s}{'Cgd/W':>16s}{'Cgs/W':>16s}{'Vov':>16s}\n")

            for row in data_interp:
                vgs, vth, gm, id_val, gds, cgg, cgs_val, cgd_val = row
                gm = abs(gm)
                id_val = abs(id_val)
                gds = abs(gds)
                cgg = abs(cgg)
                cgs_val = abs(cgs_val)
                cgd_val = abs(cgd_val)

                if id_val < 1e-15 or gm < 1e-18:
                    continue

                gm_id = gm / id_val
                gm_gds = gm / gds if gds > 1e-18 else 0
                id_w = id_val / W
                ft_val = gm / (2 * np.pi * cgg) if cgg > 1e-25 else 0
                cgg_w = cgg / W
                cgd_w = cgd_val / W
                cgs_w = cgs_val / W
                vov = vgs - vth

                f.write(f"{gm_id:16.6e}{gm_gds:16.6e}{id_w:16.6e}{ft_val:16.6e}{cgg_w:16.6e}{cgd_w:16.6e}{cgs_w:16.6e}{vov:16.6e}\n")

        count += 1

    print(f"{corner}/{target_temp}C: {count} files generated")

print(f"\nDone! Interpolated LUT at {target_temp}C saved to {{corner}}/{target_temp}C/")
