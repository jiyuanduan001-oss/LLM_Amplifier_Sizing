"""
Plot output-referred noise spectral density vs frequency
for two corners: FF/40°C (design) and SS/70°C.

Runs ngspice .noise analysis directly and exports onoise_spectrum.
"""

import subprocess, os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

BASE = "/rdf/shared/design_automation/Analog_Sizing/CircuitCollector/CircuitCollector"
PDK = f"{BASE}/PDK/sky130_pdk/libs.tech/ngspice"
CIRCUIT_PARAMS = f"{BASE}/output/opamp/tsm/temp_circuit_params.txt"
OUT_DIR = "/tmp/noise_plot"
os.makedirs(OUT_DIR, exist_ok=True)

CORNERS = [
    ("ff", 40, "FF / 40°C (design corner)"),
    ("ss", 70, "SS / 70°C"),
]


def make_netlist(corner: str, temp: int, tag: str) -> str:
    """Generate a minimal netlist for .noise analysis."""
    netlist = f"""\
Output-referred noise spectrum — {corner.upper()}/{temp}°C

.include {CIRCUIT_PARAMS}

.param mc_mm_switch=0
.param mc_pr_switch=0
.include {PDK}/corners/{corner}.spice
.include {PDK}/r+c/res_typical__cap_typical.spice
.include {PDK}/r+c/res_typical__cap_typical__lin.spice
.include {PDK}/corners/{corner}/specialized_cells.spice

.PARAM supply_voltage = 1.8
.PARAM VCM_ratio = 0.5
.PARAM PARAM_CLOAD = 5.0p
.PARAM Ib = 1e-05

V1 vdd 0 'supply_voltage'
V2 vss 0 0

* Noise TB — open-loop with ideal DC feedback
Vn_indc nsopin 0 'supply_voltage*VCM_ratio'
Vn_in ns_signal_in 0 dc 'supply_voltage*VCM_ratio' ac 1
Ln_fb nsopout nsopout_dc 1T
Cn_in nsopout_dc ns_signal_in 1T
Ib8 Ib8 gnda DC='Ib'
x8 vss vdd nsopout_dc nsopin nsopout Ib8 tsm
Cload8 nsopout 0 'PARAM_CLOAD'

.control
set filetype=ascii
option temp={temp}

noise V(nsopout) Vn_in dec 50 0.1 1G

* Detect the ngspice inoise/onoise swap bug
setplot noise1
let raw_in_0 = inoise_spectrum[0]
let raw_on_0 = onoise_spectrum[0]
let is_normal = (raw_on_0 ge raw_in_0)

* Export onoise_spectrum (the correct one) to a wrdata file
* wrdata writes: freq  real  imag
if is_normal
  wrdata {OUT_DIR}/onoise_{tag}.csv onoise_spectrum
else
  wrdata {OUT_DIR}/onoise_{tag}.csv inoise_spectrum
end

quit
.endc
.end
"""
    path = f"{OUT_DIR}/noise_{tag}.cir"
    with open(path, "w") as f:
        f.write(netlist)
    return path


def run_ngspice(netlist_path: str) -> None:
    """Run ngspice in batch mode."""
    NGSPICE = "/rdf/Applications/ngspice/bin/ngspice"
    result = subprocess.run(
        [NGSPICE, "-b", netlist_path],
        capture_output=True, text=True, timeout=120,
    )
    if result.returncode != 0:
        print(f"ngspice stderr:\n{result.stderr[-2000:]}")
        raise RuntimeError(f"ngspice failed with code {result.returncode}")


def read_wrdata(path: str):
    """Parse ngspice wrdata output (whitespace-separated: freq real imag)."""
    freq, vals = [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                try:
                    fr = float(parts[0])
                    v = float(parts[1])
                    if fr > 0:
                        freq.append(fr)
                        vals.append(v)
                except ValueError:
                    continue
    return np.array(freq), np.array(vals)


def main():
    results = {}
    for corner, temp, label in CORNERS:
        tag = f"{corner}_{temp}"
        print(f"Running noise sim: {corner.upper()}/{temp}°C ...")
        netlist = make_netlist(corner, temp, tag)
        run_ngspice(netlist)
        csv_path = f"{OUT_DIR}/onoise_{tag}.csv"
        freq, onoise = read_wrdata(csv_path)
        results[label] = (freq, onoise)
        print(f"  Got {len(freq)} frequency points, "
              f"onoise range: {onoise.min():.2e} – {onoise.max():.2e} V/√Hz")

    # --- Plot 1: Full spectrum (log-log) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    colors = ["#2563eb", "#dc2626"]
    for (label, (freq, onoise)), color in zip(results.items(), colors):
        ax.loglog(freq, onoise, label=label, color=color, linewidth=1.5)

    ax.set_xlabel("Frequency (Hz)", fontsize=12)
    ax.set_ylabel("Output-Referred Noise Density (V/√Hz)", fontsize=12)
    ax.set_title("Output-Referred Noise Spectral Density — TSM OTA", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, which="both", ls="--", alpha=0.4)
    ax.set_xlim(0.1, 1e9)

    plot_path = f"{OUT_DIR}/onoise_spectrum.png"
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    print(f"\nPlot 1 (full spectrum) saved to: {plot_path}")
    plt.close(fig)

    # --- Plot 2: Zoom on 1 MHz – 1 GHz (log-log) to show peaking region ---
    fig, ax = plt.subplots(figsize=(10, 6))
    for (label, (freq, onoise)), color in zip(results.items(), colors):
        mask = freq >= 1e6
        ax.loglog(freq[mask], onoise[mask], label=label, color=color, linewidth=1.5)

    # Mark GBW for each corner
    gbw_vals = {"FF / 40°C (design corner)": 60.5e6, "SS / 70°C": 49.1e6}
    for (label, (freq, onoise)), color in zip(results.items(), colors):
        gbw = gbw_vals.get(label, None)
        if gbw:
            mask = freq >= 1e6
            f_z = freq[mask]
            n_z = onoise[mask]
            # Interpolate onoise at GBW
            idx = np.searchsorted(f_z, gbw)
            if 0 < idx < len(f_z):
                noise_at_gbw = np.interp(gbw, f_z, n_z)
                ax.axvline(gbw, color=color, ls='--', alpha=0.5, linewidth=1)
                ax.annotate(f'GBW={gbw/1e6:.0f}MHz', xy=(gbw, noise_at_gbw),
                           xytext=(gbw*1.5, noise_at_gbw*3),
                           arrowprops=dict(arrowstyle='->', color=color, alpha=0.7),
                           fontsize=10, color=color)

    ax.set_xlabel("Frequency (Hz)", fontsize=12)
    ax.set_ylabel("Output-Referred Noise Density (V/√Hz)", fontsize=12)
    ax.set_title("Output-Referred Noise — Zoom Near GBW", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, which="both", ls="--", alpha=0.4)
    ax.set_xlim(1e6, 1e9)

    plot_path2 = f"{OUT_DIR}/onoise_spectrum_zoom.png"
    fig.tight_layout()
    fig.savefig(plot_path2, dpi=150)
    print(f"Plot 2 (zoom near GBW) saved to: {plot_path2}")
    plt.close(fig)

    # --- Plot 3: Cumulative integrated output noise (V²) vs frequency ---
    fig, ax = plt.subplots(figsize=(10, 6))
    for (label, (freq, onoise)), color in zip(results.items(), colors):
        # Trapezoidal integration of onoise² over frequency
        df = np.diff(freq)
        avg_noise2 = 0.5 * (onoise[:-1]**2 + onoise[1:]**2)
        cumulative_v2 = np.cumsum(avg_noise2 * df)
        cumulative_vrms = np.sqrt(cumulative_v2)
        ax.semilogx(freq[1:], cumulative_vrms * 1e3, label=label, color=color, linewidth=1.5)

    ax.set_xlabel("Frequency (Hz)", fontsize=12)
    ax.set_ylabel("Cumulative Integrated Output Noise (mV rms)", fontsize=12)
    ax.set_title("Cumulative Output Noise vs Frequency — TSM OTA", fontsize=13)
    ax.legend(fontsize=11)
    ax.grid(True, which="both", ls="--", alpha=0.4)
    ax.set_xlim(0.1, 1e9)

    plot_path3 = f"{OUT_DIR}/onoise_cumulative.png"
    fig.tight_layout()
    fig.savefig(plot_path3, dpi=150)
    print(f"Plot 3 (cumulative noise) saved to: {plot_path3}")
    plt.close(fig)


if __name__ == "__main__":
    main()
