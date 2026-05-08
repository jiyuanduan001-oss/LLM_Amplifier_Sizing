#!/usr/bin/env python3
"""
Post-process initial LUTs into gm/ID-indexed processed LUTs.

Reads   : asset_new/<device>/<corner>/<tempC>/initial/gmid_<device>_L<nm>n.txt
Writes  : asset_new/<device>/<corner>/<tempC>/processed/gmid_<device>_L<nm>n.txt

Initial columns (10): vgs, vth, vdsat, gm, id, gds, cgg, cgs, cgd, cdb
Processed columns (11):
    gm/id, gm/gds, id/W, ft, Cgg/W, Cgd/W, Cgs/W, Cdb/W, vgs, vth, vdsat

`vdsat` is the BSIM4 internal saturation voltage |VDS|_sat (positive
magnitude for both polarities; minimum |VDS| at which the device is in
saturation, accounting for velocity-saturation and short-channel effects).
It is the canonical voltage axis used by every downstream sizing flow for
headroom / saturation-margin / cascode-bias calculations.

All conductance/capacitance/current magnitudes are absolute-valued so the
tables for nfet and pfet look identical in shape and can be interpolated
with the same code paths.
"""
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ASSET_NEW = Path("/rdf/shared/design_automation/Analog_Sizing/AnalogAgent/asset_new")
W = 2e-6   # 2 um
DEVICES = ["nfet_01v8", "pfet_01v8"]
CORNERS = ["tt", "ff", "ss", "fs", "sf"]
TEMPS   = ["-40C", "25C", "85C"]

# Column order in processed file
PROC_COLS = ["gm/id", "gm/gds", "id/W", "ft",
             "Cgg/W", "Cgd/W", "Cgs/W", "Cdb/W",
             "vgs",   "vth",   "vdsat"]


def process_file(infile: Path, outfile: Path, device: str, corner: str, temp: str):
    gm_id, gm_gds, id_W, ft      = [], [], [], []
    cgg_W, cgd_W, cgs_W, cdb_W   = [], [], [], []
    vgs_col, vth_col, vdsat_col  = [], [], []

    with open(infile) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            try:
                v = list(map(float, line.split()))
            except ValueError:
                continue
            if len(v) < 10:
                continue
            # initial columns: vgs vth vdsat gm id gds cgg cgs cgd cdb
            v_gs  = v[0]
            v_th  = v[1]
            v_dst = v[2]
            gm    = abs(v[3])
            idv   = abs(v[4])
            gds   = abs(v[5])
            cgg   = abs(v[6])
            cgs   = abs(v[7])
            cgd   = abs(v[8])
            cdb   = abs(v[9])

            if idv < 1e-15 or gm < 1e-18:
                continue

            gm_id.append(gm / idv)
            gm_gds.append(gm / gds if gds > 1e-18 else 0.0)
            id_W.append(idv / W)
            ft.append(gm / (2 * np.pi * cgg) if cgg > 1e-25 else 0.0)
            cgg_W.append(cgg / W)
            cgd_W.append(cgd / W)
            cgs_W.append(cgs / W)
            cdb_W.append(cdb / W)
            vgs_col.append(v_gs)
            vth_col.append(v_th)
            vdsat_col.append(v_dst)

    if not gm_id:
        return 0

    # --- Trim sub-threshold branch ----------------------------------------
    # The VGS sweep produces a gm/id curve that rises toward a peak at the
    # edge of weak inversion, then falls through strong inversion.  Only the
    # strong-inversion side of the peak is usable for sizing.  We locate the
    # peak and keep the side whose far endpoint has the larger id/W.
    # If the peak is at a boundary the sub-threshold region was never swept
    # and no trimming is needed.
    gm_id_arr = np.array(gm_id)
    id_W_arr  = np.array(id_W)
    peak_idx  = int(np.argmax(gm_id_arr))

    if 0 < peak_idx < len(gm_id_arr) - 1:
        left_far_idw  = abs(id_W_arr[0])
        right_far_idw = abs(id_W_arr[-1])
        if right_far_idw >= left_far_idw:
            # Strong inversion is on the right (after peak) — typical for NFET
            keep_start, keep_end = peak_idx, len(gm_id_arr)
        else:
            # Strong inversion is on the left (before peak) — typical for PFET
            keep_start, keep_end = 0, peak_idx + 1
    else:
        keep_start, keep_end = 0, len(gm_id_arr)

    # Apply trim to all columns
    all_cols = [gm_id, gm_gds, id_W, ft, cgg_W, cgd_W, cgs_W, cdb_W,
                vgs_col, vth_col, vdsat_col]
    cols = [c[keep_start:keep_end] for c in all_cols]

    L_nm = int(infile.stem.split("_L")[1].rstrip("n"))
    L_um = L_nm / 1000.0

    outfile.parent.mkdir(parents=True, exist_ok=True)
    with open(outfile, "w") as fh:
        fh.write(f"# sky130 {device} gm/ID Processed Lookup Table\n")
        fh.write(f"# Corner: {corner}\n")
        fh.write(f"# Temperature: {temp}\n")
        fh.write(f"# W = {W*1e6:.1f} um\n")
        fh.write(f"# L = {L_um:.4g} um ({L_nm} nm)\n")
        fh.write("# Columns: gm/id [1/V]  gm/gds [V/V]  id/W [A/m]  ft [Hz]  "
                 "Cgg/W [F/m]  Cgd/W [F/m]  Cgs/W [F/m]  Cdb/W [F/m]  "
                 "vgs [V]  vth [V]  vdsat [V]\n")
        fh.write("# vdsat = BSIM4 saturation voltage (|VDS|_sat, positive); "
                 "use for headroom / saturation / cascode-bias calculations\n")
        hdr = "#" + "".join(lbl.rjust(16) for lbl in PROC_COLS)
        fh.write(hdr + "\n")
        for j in range(len(cols[0])):
            fh.write("".join(f"{col[j]:16.6e}" for col in cols) + "\n")

    return len(cols[0])


def main():
    total_files = 0
    t0 = __import__("time").time()
    for device in DEVICES:
        for corner in CORNERS:
            for temp in TEMPS:
                indir  = ASSET_NEW / device / corner / temp / "initial"
                outdir = ASSET_NEW / device / corner / temp / "processed"
                if not indir.is_dir():
                    continue
                files = sorted(indir.glob(f"gmid_{device}_L*n.txt"),
                               key=lambda p: int(p.stem.split("_L")[1].rstrip("n")))
                n_ok = 0
                for f in files:
                    out = outdir / f.name
                    if process_file(f, out, device, corner, temp):
                        n_ok += 1
                total_files += n_ok
                print(f"{device}/{corner}/{temp}: {n_ok}/{len(files)} processed → {outdir}")

    print(f"\nDone. {total_files} processed LUT files written in "
          f"{__import__('time').time()-t0:.1f}s.")


if __name__ == "__main__":
    main()
