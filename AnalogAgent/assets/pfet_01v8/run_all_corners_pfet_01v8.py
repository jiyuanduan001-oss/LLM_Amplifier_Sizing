#!/usr/bin/env python3
"""
Run PMOS pfet_01v8 gm/ID characterization for all corners and temperatures.
Generates SPICE, runs ngspice, converts wrdata to formatted LUT files.

Output structure:
  {corner}/{temp}C/gmid_pfet_01v8_L{nm}n.txt

Run in WSL:  python3 /mnt/d/SKYWATER130_LUT/pmos/run_all_corners.py
"""
import os
import subprocess
import sys
import time

# === Configuration ===
PDK_LIB = "/usr/local/share/pdk/sky130A/libs.tech/ngspice/sky130.lib.spice"
MODEL_NAME = "sky130_fd_pr__pfet_01v8"
DEVICE = "pfet_01v8"
VDD = 1.8
VD = 1.2      # VSD = 0.6V
W = 2         # in scale units (um due to option scale=1e-6)

CORNERS = ["tt", "ff", "ss", "fs", "sf"]
TEMPS = [0, 25, 75]

L_VALUES_NM = list(range(180, 5941, 180))  # 33 values
BATCH_SIZE = 13

WORK_DIR = "/tmp/pmos_char"
OUT_BASE = "/mnt/d/SKYWATER130_LUT/pmos"


def generate_spice(corner, temp, l_values, batch_idx, start_dev_idx):
    """Generate a SPICE netlist for one batch."""
    lines = []
    lines.append(f"* Sky130 {DEVICE} gm/ID LUT - {corner}/{temp}C batch{batch_idx}")
    lines.append(f".lib {PDK_LIB} {corner}")
    lines.append(f".temp {temp}")
    lines.append(f"VDD vdd 0 {VDD}")
    lines.append(f"VG vg 0 0.9")
    lines.append(f"VD_bias vd 0 {VD}")
    lines.append("")

    for i, l_nm in enumerate(l_values):
        n = i + 1
        l_um = l_nm / 1000.0
        lines.append(f"XM{n} d{n} vg vdd vdd {MODEL_NAME} W={W} L={l_um}")
        lines.append(f"VD{n} vd d{n} 0")

    lines.append("")
    lines.append(".option wnflag=1")
    lines.append(".option savecurrents")
    lines.append("")
    lines.append(".control")
    lines.append("save all")

    for i in range(len(l_values)):
        n = i + 1
        for p in ["gm", "vth", "gds", "cgg", "cgs", "cgd"]:
            lines.append(f"save @m.xm{n}.m{MODEL_NAME}[{p}]")

    lines.append("")
    lines.append("dc VG 0 1.8 5m")
    lines.append("remzerovec")
    lines.append("")

    for i, l_nm in enumerate(l_values):
        n = i + 1
        g = start_dev_idx + i
        out = os.path.join(WORK_DIR, f"{corner}_{temp}C_{g}.txt")
        params = [
            f"@m.xm{n}.m{MODEL_NAME}[gm]",
            f"i(VD{n})",
            f"@m.xm{n}.m{MODEL_NAME}[vth]",
            f"@m.xm{n}.m{MODEL_NAME}[gds]",
            f"@m.xm{n}.m{MODEL_NAME}[cgg]",
            f"@m.xm{n}.m{MODEL_NAME}[cgs]",
            f"@m.xm{n}.m{MODEL_NAME}[cgd]",
        ]
        lines.append(f"wrdata {out} {' '.join(params)}")

    lines.append("")
    lines.append("quit 0")
    lines.append(".endc")
    lines.append(".end")
    return "\n".join(lines)


def convert_wrdata(raw_file, corner, temp, l_nm):
    """Convert one wrdata file to formatted LUT."""
    l_um = l_nm / 1000.0
    rows = []

    with open(raw_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                vals = list(map(float, line.split()))
                if len(vals) >= 14:
                    vg     = vals[0]
                    gm     = vals[1]
                    id_val = vals[3]
                    vth    = vals[5]
                    gds    = vals[7]
                    cgg    = vals[9]
                    cgs    = vals[11]
                    cgd    = vals[13]
                    vgs    = vg - VDD  # VGS = VG - VS = VG - VDD
                    rows.append([vgs, vth, gm, id_val, gds, cgg, cgs, cgd])
            except (ValueError, IndexError):
                continue

    if not rows:
        return None

    out_dir = os.path.join(OUT_BASE, corner, f"{temp}C")
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"gmid_{DEVICE}_L{l_nm}n.txt")

    with open(out_file, "w") as f:
        f.write(f"# sky130 {DEVICE} gm/ID Lookup Table\n")
        f.write(f"# Corner: {corner}\n")
        f.write(f"# Temperature: {temp} C\n")
        f.write(f"# W = {W:.1f} um\n")
        f.write(f"# L = {l_um:.4g} um ({l_nm} nm)\n")
        f.write(f"# VDS = -0.6 V  (VSD = 0.6 V)\n")
        f.write("# Columns: vgs [V]  vth [V]  gm [S]  id [A]  gds [S]  cgg [F]  cgs [F]  cgd [F]\n")
        hdr = "#" + "vgs".rjust(15) + "vth".rjust(16) + "gm".rjust(16) + "id".rjust(16)
        hdr += "gds".rjust(16) + "cgg".rjust(16) + "cgs".rjust(16) + "cgd".rjust(16)
        f.write(hdr + "\n")
        for row in rows:
            f.write("".join(f"{v:16.6e}" for v in row) + "\n")

    return len(rows)


def main():
    os.makedirs(WORK_DIR, exist_ok=True)

    total = len(CORNERS) * len(TEMPS)
    done = 0
    t0 = time.time()

    for corner in CORNERS:
        for temp in TEMPS:
            done += 1
            print(f"\n[{done}/{total}] {corner}/{temp}C", flush=True)

            # Split L values into batches
            batches = []
            for i in range(0, len(L_VALUES_NM), BATCH_SIZE):
                batches.append(L_VALUES_NM[i:i+BATCH_SIZE])

            dev_idx = 0
            batch_ok = True
            for bi, batch_l in enumerate(batches):
                # Generate SPICE
                spice = generate_spice(corner, temp, batch_l, bi, dev_idx)
                spice_file = os.path.join(WORK_DIR, f"run_{corner}_{temp}C_b{bi}.spice")
                with open(spice_file, "w") as f:
                    f.write(spice)

                # Run ngspice
                print(f"  batch {bi+1}/{len(batches)}: L={batch_l[0]}n-{batch_l[-1]}n ...", end=" ", flush=True)
                result = subprocess.run(
                    ["ngspice", "-b", spice_file],
                    capture_output=True, text=True, timeout=300
                )
                if result.returncode != 0:
                    print("FAILED")
                    batch_ok = False
                    dev_idx += len(batch_l)
                    continue
                print("OK", flush=True)

                # Convert each L
                for i, l_nm in enumerate(batch_l):
                    g = dev_idx + i
                    raw = os.path.join(WORK_DIR, f"{corner}_{temp}C_{g}.txt")
                    if os.path.exists(raw):
                        n = convert_wrdata(raw, corner, temp, l_nm)
                        if n is None:
                            print(f"    WARN: no data for L={l_nm}n")
                    else:
                        print(f"    WARN: {raw} missing")

                dev_idx += len(batch_l)

            # Count output
            out_dir = os.path.join(OUT_BASE, corner, f"{temp}C")
            if os.path.exists(out_dir):
                cnt = len([f for f in os.listdir(out_dir) if f.endswith(".txt")])
                elapsed = time.time() - t0
                print(f"  -> {cnt} LUT files  (elapsed: {elapsed:.0f}s)")

    print(f"\n{'='*50}")
    print(f"All done! {total} corner/temp combos in {time.time()-t0:.0f}s")
    print(f"Output: {OUT_BASE}/{{corner}}/{{temp}}C/")


if __name__ == "__main__":
    main()
