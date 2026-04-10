import numpy as np
import os
import glob

# === Configuration ===
import platform
if platform.system() == "Windows":
    base_path = r"D:\SKYWATER130_LUT\pmos"
else:
    base_path = "/mnt/d/SKYWATER130_LUT/pmos"
device = "pfet_01v8"
W = 2e-6  # 2um

corners = ["tt", "fs", "sf", "ff", "ss"]
temps = ["0C", "25C", "75C"]

for corner in corners:
    for temp in temps:
        path = os.path.join(base_path, corner, temp)
        outdir = os.path.join(base_path, corner, temp, "processed")
        os.makedirs(outdir, exist_ok=True)

        files = sorted(glob.glob(os.path.join(path, f"gmid_{device}_L*n.txt")),
                       key=lambda f: int(os.path.basename(f).split("_L")[1].split("n.txt")[0]))

        for filename in files:
            L_nm = int(os.path.basename(filename).split("_L")[1].split("n.txt")[0])
            L_um = L_nm / 1000.0

            _gm_id = []
            _gm_gds = []
            _id_W = []
            _ft = []
            _cgg_W = []
            _cgd_W = []
            _cgs_W = []
            _Vov = []

            with open(filename, 'r') as f:
                for line in f:
                    if line.startswith('#'):
                        continue
                    try:
                        vals = list(map(float, line.strip().split()))
                        if len(vals) < 8:
                            continue
                        # Columns: vgs vth gm id gds cgg cgs cgd
                        v_gs = vals[0]
                        v_th = vals[1]
                        gm = abs(vals[2])
                        id_val = abs(vals[3])
                        gds = abs(vals[4])
                        cgg = abs(vals[5])
                        cgs_val = abs(vals[6])
                        cgd_val = abs(vals[7])

                        if id_val < 1e-15 or gm < 1e-18:
                            continue

                        _gm_id.append(gm / id_val)
                        _gm_gds.append(gm / gds if gds > 1e-18 else 0)
                        _id_W.append(id_val / W)
                        _ft.append(gm / (2 * np.pi * cgg) if cgg > 1e-25 else 0)
                        _cgg_W.append(cgg / W)
                        _cgd_W.append(cgd_val / W)
                        _cgs_W.append(cgs_val / W)
                        _Vov.append(v_gs - v_th)

                    except (ValueError, IndexError):
                        continue

            # Truncate non-monotonic tail: gm/id should increase monotonically
            # as |VGS| decreases (strong inv -> subthreshold). Near VGS~0 the
            # device is off and gm/id becomes noisy. Find the peak of gm/id
            # and discard everything after it.
            if len(_gm_id) > 1:
                peak_idx = max(range(len(_gm_id)), key=lambda i: _gm_id[i])
                n_keep = peak_idx + 1
                _gm_id  = _gm_id[:n_keep]
                _gm_gds = _gm_gds[:n_keep]
                _id_W   = _id_W[:n_keep]
                _ft     = _ft[:n_keep]
                _cgg_W  = _cgg_W[:n_keep]
                _cgd_W  = _cgd_W[:n_keep]
                _cgs_W  = _cgs_W[:n_keep]
                _Vov    = _Vov[:n_keep]

            # Write processed file
            out_file = os.path.join(outdir, f"gmid_{device}_L{L_nm}n.txt")
            with open(out_file, 'w') as f:
                f.write(f"# sky130 {device} gm/ID Processed Lookup Table\n")
                f.write(f"# Corner: {corner}\n")
                f.write(f"# Temperature: {temp}\n")
                f.write(f"# W = {W*1e6:.1f} um\n")
                f.write(f"# L = {L_um:.4g} um ({L_nm} nm)\n")
                f.write(f"# Columns: gm/id [1/V]  gm/gds [V/V]  id/W [A/m]  ft [Hz]  Cgg/W [F/m]  Cgd/W [F/m]  Cgs/W [F/m]  Vov [V]\n")
                f.write(f"#{'gm/id':>14s}{'gm/gds':>16s}{'id/W':>16s}{'ft':>16s}{'Cgg/W':>16s}{'Cgd/W':>16s}{'Cgs/W':>16s}{'Vov':>16s}\n")
                for j in range(len(_gm_id)):
                    f.write(f"{_gm_id[j]:16.6e}{_gm_gds[j]:16.6e}{_id_W[j]:16.6e}{_ft[j]:16.6e}{_cgg_W[j]:16.6e}{_cgd_W[j]:16.6e}{_cgs_W[j]:16.6e}{_Vov[j]:16.6e}\n")

        count = len(files)
        print(f"{corner}/{temp}: {count} files -> {outdir}")

print("\nDone! All processed LUT files generated.")
