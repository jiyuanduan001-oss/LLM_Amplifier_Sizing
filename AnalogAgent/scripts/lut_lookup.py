"""
LUT lookup utilities for gm/Id characterization data.

Processed LUT files live under:
    asset_new/{device}/{corner}/{temp}/processed/gmid_{device}_L{l_nm}n.txt

Each .txt file is space-separated with ``#``-prefixed comment headers and
eleven data columns:

    gm/id [1/V]  gm/gds [V/V]  id/W [A/m]  ft [Hz]
    Cgg/W [F/m]  Cgd/W [F/m]  Cgs/W [F/m]  Cdb/W [F/m]
    vgs [V]      vth [V]      vdsat [V]

The DataFrame returned by :func:`load_lut` uses these clean column names:

    gm_id  gm_gds  id_w  ft  cgg_w  cgd_w  cgs_w  cdb_w  vgs  vth  vdsat

Unit notes (backward-compatible with bridge code):
    * id_w  – stored A/m, numerically identical to µA/µm (1 A/m = 1 µA/µm)
    * cgg_w, cgd_w, cgs_w, cdb_w – stored F/m, kept as-is
    * ft    – stored Hz, kept as-is
    * gm_gds – stored directly (no inversion needed)
    * vgs, vth, vdsat – V (vth and vdsat are positive magnitudes for both
      polarities; ngspice convention)

`vdsat` is the BSIM4 internal saturation voltage (|VDS|_sat including
velocity-saturation / short-channel effects). It is the canonical quantity
for all headroom, saturation-margin, and cascode-bias calculations. The
LUT does not carry a square-law overdrive column — `vdsat`, `vth`, and
`vgs` are the only voltage axes exposed.

Filename convention:
    gmid_{device}_L{l_nm}n.txt   e.g. gmid_nfet_01v8_L180n.txt

Device naming:
    Accepts 'nfet', 'pfet', 'nfet_01v8', 'pfet_01v8'.
    Short forms are mapped to their full PDK names automatically.

Available reference temperatures (post-migration to asset_new):
    -40C, 25C, 85C  per corner (5 corners: tt, ff, ss, fs, sf).
First-order linear interpolation between bracketing reference temperatures
is performed automatically by load_lut() for any in-range target temp.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from functools import lru_cache
from typing import List, Optional, Union

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(__file__).parent.parent / "asset_new"

# Short-name → full PDK folder name
_DEVICE_MAP = {
    "nfet": "nfet_01v8",
    "pfet": "pfet_01v8",
    "nfet_01v8": "nfet_01v8",
    "pfet_01v8": "pfet_01v8",
}

# ---------------------------------------------------------------------------
# SKY130 extrinsic (layout-dependent) capacitance parameters
# ---------------------------------------------------------------------------
# These are NOT in the gm/ID LUT — they come from the BSIM4 model card
# and describe physical overlap and junction parasitics that the LUT's
# intrinsic cgs_w / cgd_w / cdb_w do not capture.
#
# Source: sky130_fd_pr__*fet_01v8__ff.pm3.spice (values are corner-invariant)
#
# The LUT cgd_w is the intrinsic channel-charge partition to the drain,
# which is ≈ 0 in saturation. The physical gate-drain overlap (cgdo × W)
# dominates and is 20-80× larger.
#
# The LUT cdb_w captures the area junction component for a single
# reference device. Multi-instance (high-M) devices have additional
# perimeter and gate-edge sidewall terms that scale with M.

SKY130_EXTRINSIC = {
    "nfet_01v8": {
        "cgdo":   2.4133e-10,   # F/m — gate-drain overlap per unit width
        "cgso":   2.4133e-10,   # F/m — gate-source overlap per unit width
        "cjs":    1.1311e-03,   # F/m² — drain junction area cap (zero-bias)
        "cjsws":  3.1014e-11,   # F/m — drain junction sidewall cap
        "cjswgs": 2.0113e-10,   # F/m — drain gate-edge sidewall cap per width
        "pbs":    0.729,        # V — junction built-in potential
    },
    "pfet_01v8": {
        "cgdo":   4.8684e-11,   # F/m — gate-drain overlap per unit width
        "cgso":   4.8684e-11,   # F/m — gate-source overlap per unit width
        "cjs":    6.8894e-04,   # F/m² — drain junction area cap (zero-bias)
        "cjsws":  9.2318e-11,   # F/m — drain junction sidewall cap
        "cjswgs": 2.2326e-10,   # F/m — drain gate-edge sidewall cap per width
        "pbs":    0.659,        # V — junction built-in potential
    },
}

# Default diffusion extension beyond gate (m) — used for drain area/perimeter
# estimation when layout details are unavailable.
_DIFF_EXT_M = 0.29e-6  # 0.29 µm, typical for SKY130

# Raw file column order → clean Python names (matches asset_new processed LUT
# header: gm/id  gm/gds  id/W  ft  Cgg/W  Cgd/W  Cgs/W  Cdb/W  vgs  vth  vdsat)
_RAW_COLUMNS = ["gm_id", "gm_gds", "id_w", "ft",
                "cgg_w", "cgd_w", "cgs_w", "cdb_w",
                "vgs",   "vth",   "vdsat"]

# Metrics that lut_query supports
_VALID_METRICS = set(_RAW_COLUMNS)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _resolve_device(device: str) -> str:
    """Map any accepted device alias to the canonical folder name."""
    canonical = _DEVICE_MAP.get(device)
    if canonical is None:
        raise KeyError(
            f"Unknown device '{device}'. "
            f"Accepted names: {sorted(_DEVICE_MAP.keys())}"
        )
    return canonical


def _lut_dir(device: str, corner: str, temp) -> Path:
    """Return the processed-LUT directory for a device/corner/temp combo."""
    return ASSETS_DIR / device / corner / str(temp) / "processed"


# ---------------------------------------------------------------------------
# Core I/O
# ---------------------------------------------------------------------------

def _parse_temp(temp) -> int:
    """Extract numeric temperature from a string like '25C' or '75C', or an int/float."""
    if isinstance(temp, (int, float)):
        return int(temp)
    return int(str(temp).rstrip("Cc"))


def _discover_temps(device: str, corner: str) -> List[int]:
    """Return sorted list of available reference temperatures (°C) for a device/corner."""
    corner_dir = ASSETS_DIR / device / corner
    if not corner_dir.exists():
        return []
    temps = []
    for d in corner_dir.iterdir():
        if d.is_dir() and (d / "processed").exists():
            try:
                temps.append(_parse_temp(d.name))
            except ValueError:
                continue
    temps.sort()
    return temps


def _load_processed_file(fpath: Path) -> pd.DataFrame:
    """Read a single processed LUT file into a DataFrame."""
    return pd.read_csv(
        fpath,
        sep=r"\s+",
        comment="#",
        header=None,
        names=_RAW_COLUMNS,
    )


def _trim_to_strong_inversion(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop the sub-threshold branch so gm_id is monotonic across the table.

    Raw processed LUTs sweep VGS across the full range. gm/Id is not
    monotonic in VGS: it rises from a low value in strong inversion
    toward a peak (~25–30 S/A) at the onset of weak inversion, then
    falls again as the device enters deep sub-threshold. The two sides
    of the peak are therefore two physical branches sharing the same
    gm/Id axis:

      * strong-inversion side — large Id/W (usable for sizing)
      * sub-threshold side    — Id/W → 0       (unusable, but present
                                                 in the raw table)

    np.interp on the full table silently lands on whichever side happens
    to bracket the query. For the SKY130 25 °C NFET at gm/Id = 13 the
    sub-threshold row (Id/W ≈ 6e-7) bracketed the query and the lookup
    returned Id/W ≈ 0.18 A/m instead of the physically-correct
    ≈ 0.80 A/m — a ~4.6× sizing error.

    This function locates the peak and returns only the strong-inversion
    branch. Which side of the peak that is depends on the sweep
    direction (NFET sweeps VGS 0→+, PFET sweeps VGS −→0), so we pick
    the half whose far end has the larger Id/W — that is the physical
    strong-inversion branch regardless of polarity.
    """
    if df.empty or "gm_id" not in df.columns or "id_w" not in df.columns:
        return df

    peak_idx = int(df["gm_id"].idxmax())
    if peak_idx == 0 or peak_idx == len(df) - 1:
        # Table already monotonic in gm_id (no sub-threshold branch present).
        return df.reset_index(drop=True)

    left  = df.iloc[: peak_idx + 1]   # includes peak
    right = df.iloc[peak_idx:]        # includes peak

    # The strong-inversion branch is the side whose far endpoint has
    # larger Id/W. Using the endpoints (not means) keeps the rule
    # robust to sub-threshold tails that may contain near-zero rows.
    left_far_idw  = abs(left["id_w"].iloc[0])
    right_far_idw = abs(right["id_w"].iloc[-1])

    chosen = right if right_far_idw >= left_far_idw else left
    return chosen.reset_index(drop=True)


def _interpolate_lut(
    device: str,
    l_nm: int,
    corner: str,
    target_c: int,
    t_lo: int,
    t_hi: int,
) -> pd.DataFrame:
    """
    Linearly interpolate a processed LUT between two reference temperatures.

    Returns a DataFrame with the same columns as a regular processed LUT.
    """
    alpha = (target_c - t_lo) / (t_hi - t_lo)

    dir_lo = _lut_dir(device, corner, f"{t_lo}C")
    dir_hi = _lut_dir(device, corner, f"{t_hi}C")
    fname = f"gmid_{device}_L{l_nm}n.txt"

    f_lo = dir_lo / fname
    f_hi = dir_hi / fname

    if not f_lo.exists():
        raise FileNotFoundError(
            f"Reference LUT not found for interpolation: {f_lo}"
        )
    if not f_hi.exists():
        raise FileNotFoundError(
            f"Reference LUT not found for interpolation: {f_hi}"
        )

    df_lo = _load_processed_file(f_lo)
    df_hi = _load_processed_file(f_hi)

    # Trim each source to its strong-inversion branch before row-wise blending.
    # The sub-threshold tail varies strongly with temperature and contains a
    # non-monotonic gm_id axis — blending it row-by-row produces garbage.
    # Trimming first aligns both tables at their gm_id peak, so row-index
    # blending mixes comparable operating points.
    df_lo = _trim_to_strong_inversion(df_lo)
    df_hi = _trim_to_strong_inversion(df_hi)

    # Align to the shorter table (same VGS sweep expected)
    n = min(len(df_lo), len(df_hi))
    df_lo = df_lo.iloc[:n].reset_index(drop=True)
    df_hi = df_hi.iloc[:n].reset_index(drop=True)

    # Linear interpolation on all columns
    df_interp = df_lo * (1 - alpha) + df_hi * alpha

    return df_interp


@lru_cache(maxsize=128)
def load_lut(
    device: str,
    l_nm: int,
    corner: str = "tt",
    temp: str = "25C",
) -> pd.DataFrame:
    """
    Load a gm/Id LUT for a given device, channel length, corner, and temp.

    If the exact temperature is not available on disk, automatically performs
    first-order linear interpolation between the two nearest bracketing
    reference temperatures.

    Args:
        device:  Device name — 'nfet', 'pfet', 'nfet_01v8', or 'pfet_01v8'.
        l_nm:    Channel length in nanometers (integer, e.g. 180).
        corner:  Process corner — 'tt', 'ff', 'ss', 'fs', 'sf'.
        temp:    Temperature string — '-40C', '25C', '85C' (reference
                 temps). Other in-range values are linearly interpolated.

    Returns:
        DataFrame with columns:
            gm_id, gm_gds, id_w, ft, cgg_w, cgd_w, cgs_w, cdb_w,
            vgs, vth, vdsat
    """
    canonical = _resolve_device(device)
    directory = _lut_dir(canonical, corner, temp)
    fname = directory / f"gmid_{canonical}_L{l_nm}n.txt"

    if fname.exists():
        # Exact temperature file found — load directly, then drop the
        # sub-threshold branch so gm_id is monotonic (see
        # _trim_to_strong_inversion for the full rationale).
        df = pd.read_csv(
            fname,
            sep=r"\s+",
            comment="#",
            header=None,
            names=_RAW_COLUMNS,
        )
        return _trim_to_strong_inversion(df)

    # --- Auto-interpolation fallback ---
    target_c = _parse_temp(temp)
    available = _discover_temps(canonical, corner)

    if not available:
        raise FileNotFoundError(
            f"No reference temperatures found for device={device}, corner={corner}"
        )

    # Find bracketing temperatures
    below = [t for t in available if t <= target_c]
    above = [t for t in available if t >= target_c]

    if not below or not above:
        raise FileNotFoundError(
            f"Cannot interpolate: target {target_c}°C is outside the available "
            f"range {available} for device={device}, corner={corner}. "
            f"Extrapolation is not supported."
        )

    t_lo = max(below)
    t_hi = min(above)

    if t_lo == t_hi:
        # Exact match exists in available list but file was missing for this L
        raise FileNotFoundError(
            f"LUT not found: {fname}\n"
            f"  device={device} ({canonical}), L={l_nm} nm, "
            f"corner={corner}, temp={temp}"
        )

    return _interpolate_lut(canonical, l_nm, corner, target_c, t_lo, t_hi)


# ---------------------------------------------------------------------------
# Main query API
# ---------------------------------------------------------------------------

def lut_query(
    device: str,
    metric: str,
    L: float,
    corner: str = "tt",
    temp: str = "25C",
    gm_id_val: Optional[float] = None,
) -> Union[pd.DataFrame, float]:
    """
    Unified LUT query — the primary API for bridge / skill code.

    Args:
        device:     'nfet', 'pfet', 'nfet_01v8', or 'pfet_01v8'.
        metric:     Column to retrieve.  One of:
                        gm_id, gm_gds, id_w, ft,
                        cgg_w, cgd_w, cgs_w, cdb_w,
                        vgs, vth, vdsat
        L:          Channel length in **micrometers** (e.g. 0.18 for 180 nm).
                    Converted to nm internally for the filename lookup.
        corner:     Process corner (default 'tt').
        temp:       Temperature string (default '25C').
        gm_id_val:  If given, linearly interpolate at this gm/Id point and
                    return a single float.  If None, return the full 2-column
                    DataFrame [gm_id, <metric>].

    Returns:
        pd.DataFrame  when gm_id_val is None (columns: gm_id, metric).
        float         when gm_id_val is provided.

    Raises:
        FileNotFoundError: LUT file does not exist.
        ValueError:        gm_id_val outside the table range.
        KeyError:          Unrecognised device or metric.
    """
    if metric not in _VALID_METRICS:
        raise KeyError(
            f"Unknown metric '{metric}'. Valid metrics: {sorted(_VALID_METRICS)}"
        )

    l_nm = int(round(L * 1000))
    df = load_lut(device, l_nm, corner=corner, temp=temp)

    series = df[metric]

    if gm_id_val is not None:
        lo, hi = df["gm_id"].min(), df["gm_id"].max()
        if not (lo <= gm_id_val <= hi):
            raise ValueError(
                f"gm_id_val={gm_id_val} is outside LUT range "
                f"[{lo:.4f}, {hi:.4f}] for device={device}, L={L} µm, "
                f"corner={corner}, temp={temp}."
            )
        # np.interp requires strictly increasing x
        sort_idx = np.argsort(df["gm_id"].values)
        return float(
            np.interp(
                gm_id_val,
                df["gm_id"].values[sort_idx],
                series.values[sort_idx],
            )
        )

    # Return the full curve as a two-column DataFrame
    return pd.DataFrame({"gm_id": df["gm_id"].values, metric: series.values})


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

def list_available_L(
    device: str,
    corner: str = "tt",
    temp: str = "25C",
) -> List[float]:
    """
    Return sorted list of available channel lengths (in µm) for a device.

    Scans the processed LUT directory for matching filenames and extracts
    the L value from each.

    Args:
        device:  Device name (any accepted alias).
        corner:  Process corner (default 'tt').
        temp:    Temperature string (default '25C').

    Returns:
        Sorted list of L values in micrometers (e.g. [0.18, 0.36, ...]).
    """
    canonical = _resolve_device(device)
    directory = _lut_dir(canonical, corner, temp)

    if not directory.exists():
        # Exact temp directory missing — fall back to nearest reference temp.
        # L values are the same across temperatures, so any reference works.
        target_c = _parse_temp(temp)
        available = _discover_temps(canonical, corner)
        if not available:
            raise FileNotFoundError(
                f"LUT directory not found: {directory}\n"
                f"  device={device} ({canonical}), corner={corner}, temp={temp}"
            )
        ref_temp = min(available, key=lambda t: abs(t - target_c))
        directory = _lut_dir(canonical, corner, f"{ref_temp}C")

    lengths_nm: List[int] = []
    prefix = f"gmid_{canonical}_L"
    for f in directory.iterdir():
        name = f.name
        if name.startswith(prefix) and name.endswith("n.txt"):
            # Extract the numeric part between 'L' and 'n.txt'
            num_str = name[len(prefix):-len("n.txt")]
            try:
                lengths_nm.append(int(num_str))
            except ValueError:
                continue

    lengths_nm.sort()
    return [l / 1000.0 for l in lengths_nm]


# ---------------------------------------------------------------------------
# Convenience wrappers (backward-compatible)
# ---------------------------------------------------------------------------

def lookup_by_gmid(
    device: str,
    l_nm: int,
    gm_id: float,
    col: str,
    corner: str = "tt",
    temp: str = "25C",
) -> float:
    """
    Look up a LUT column value at a specific gm/Id by linear interpolation.

    Args:
        device:  Device name (any accepted alias, e.g. 'nfet', 'nfet_01v8').
        l_nm:    Channel length in nm.
        gm_id:   Target gm/Id ratio (1/V).
        col:     Column name — one of the clean names:
                    gm_id, gm_gds, id_w, ft,
                    cgg_w, cgd_w, cgs_w, cdb_w,
                    vgs, vth, vdsat
        corner:  Process corner (default 'tt').
        temp:    Temperature (default '25C').
    """
    df = load_lut(device, l_nm, corner=corner, temp=temp)
    if col not in df.columns:
        raise KeyError(
            f"Column '{col}' not in LUT. Available: {list(df.columns)}"
        )
    sort_idx = np.argsort(df["gm_id"].values)
    return float(
        np.interp(gm_id, df["gm_id"].values[sort_idx], df[col].values[sort_idx])
    )


def lookup_gm_gds(
    device: str, l_nm: int, gm_id: float,
    corner: str = "tt", temp: str = "25C",
) -> float:
    """Return intrinsic gain gm/gds (V/V) for a given gm/Id and L."""
    return lookup_by_gmid(device, l_nm, gm_id, "gm_gds", corner=corner, temp=temp)


def lookup_id_w(
    device: str, l_nm: int, gm_id: float,
    corner: str = "tt", temp: str = "25C",
) -> float:
    """Return Id/W (A/m ≡ µA/µm) for a given gm/Id and L."""
    return lookup_by_gmid(device, l_nm, gm_id, "id_w", corner=corner, temp=temp)


def lookup_cgg_w(
    device: str, l_nm: int, gm_id: float,
    corner: str = "tt", temp: str = "25C",
) -> float:
    """Return Cgg/W (F/m) for a given gm/Id and L."""
    return lookup_by_gmid(device, l_nm, gm_id, "cgg_w", corner=corner, temp=temp)


def lookup_ft(
    device: str, l_nm: int, gm_id: float,
    corner: str = "tt", temp: str = "25C",
) -> float:
    """Return fT (Hz) for a given gm/Id and L."""
    return lookup_by_gmid(device, l_nm, gm_id, "ft", corner=corner, temp=temp)


# ---------------------------------------------------------------------------
# Extrinsic capacitance helpers
# ---------------------------------------------------------------------------

def extrinsic_caps(
    device: str,
    W_m: float,
    M: int = 1,
) -> dict:
    """
    Compute extrinsic (overlap + junction) capacitances not in the gm/ID LUT.

    The LUT stores *intrinsic* small-signal caps (channel charge partition).
    This function returns the *extrinsic* components from the BSIM4 model card:
      - Cgd_overlap: gate-drain overlap (cgdo × W_total)
      - Cgs_overlap: gate-source overlap (cgso × W_total)
      - Cdb_perim:   drain junction perimeter + gate-edge sidewall cap

    The returned values should be ADDED to the LUT-derived intrinsic caps.

    Args:
        device:  'nfet' or 'pfet' (or full PDK name).
        W_m:     Total device width in meters (all instances combined).
        M:       Multiplier (number of parallel instances). Used to
                 estimate drain perimeter.
                 NOTE: the geometry model assumes shared-drain
                 interdigitated layout (n_drains = ceil(M/2)), which
                 is appropriate for nf-style fingers. Our netlists use
                 m= (independent instances) where n_drains = M; this
                 causes a slight underestimate of drain perimeter.

    Returns:
        dict with keys:
            'cgd_ov':  gate-drain overlap cap (F)
            'cgs_ov':  gate-source overlap cap (F)
            'cdb_sw':  drain junction sidewall + gate-edge cap (F)
    """
    canonical = _resolve_device(device)
    ex = SKY130_EXTRINSIC.get(canonical)
    if ex is None:
        return {"cgd_ov": 0.0, "cgs_ov": 0.0, "cdb_sw": 0.0}

    W_total = W_m  # meters

    # Gate overlap caps — proportional to total width
    cgd_ov = ex["cgdo"] * W_total
    cgs_ov = ex["cgso"] * W_total

    # Drain junction perimeter estimation.
    # For M instances: W_inst = W_total / M.
    # Using shared-drain interdigitated model (n_drains = ceil(M/2)).
    # TODO: our netlists use m= (multiplier, independent instances)
    # where each instance has its own drain → n_drains should be M.
    # The shared-drain model underestimates drain perimeter for m>2.
    n_drains = max(1, (M + 1) // 2)  # shared-drain assumption
    W_inst = W_total / max(M, 1)
    P_drain = n_drains * 2 * (W_inst + _DIFF_EXT_M)

    cdb_sw = ex["cjsws"] * P_drain + ex["cjswgs"] * W_total

    return {
        "cgd_ov": cgd_ov,
        "cgs_ov": cgs_ov,
        "cdb_sw": cdb_sw,
    }


def pdk_cdb(
    device: str,
    W_m: float,
    M: int = 1,
) -> float:
    """
    Compute total drain-bulk junction cap from PDK parameters (first-principles).

    Use this INSTEAD of (cdb_w × W + extrinsic cdb_sw) when accurate Cdb
    is needed. The LUT cdb_w is characterized from a test device whose drain
    diffusion area scales with L, so it overestimates Cdb for long-channel
    devices in real layouts where drain geometry is L-independent.

    This function computes Cdb from the area and perimeter model:
        Cdb = cjs × A_drain + cjsws × P_drain + cjswgs × W_total

    Args:
        device:  'nfet' or 'pfet' (or full PDK name).
        W_m:     Total device width in meters.
        M:       Multiplier (number of parallel instances).

    Returns:
        Total drain-bulk junction capacitance in Farads (zero-bias).
    """
    canonical = _resolve_device(device)
    ex = SKY130_EXTRINSIC.get(canonical)
    if ex is None:
        return 0.0

    W_total = W_m
    W_inst = W_total / max(M, 1)
    n_drains = max(1, (M + 1) // 2)  # shared-drain assumption (see extrinsic_caps TODO)

    A_drain = n_drains * W_inst * _DIFF_EXT_M
    P_drain = n_drains * 2 * (W_inst + _DIFF_EXT_M)

    return (ex["cjs"] * A_drain
            + ex["cjsws"] * P_drain
            + ex["cjswgs"] * W_total)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli_main():
    import argparse
    import json

    parser = argparse.ArgumentParser(
        description="Query processed gm/Id LUT data."
    )
    parser.add_argument(
        "--device", required=True,
        help="Device name: nfet, pfet, nfet_01v8, pfet_01v8",
    )
    parser.add_argument(
        "--metric", required=True,
        help="Metric to query: " + " | ".join(sorted(_VALID_METRICS)),
    )
    parser.add_argument(
        "--L", type=float, required=True, nargs="+",
        help="Channel length(s) in micrometers (e.g. 0.18 0.5 1.0)",
    )
    parser.add_argument(
        "--gm_id", type=float, default=None,
        help="If given, interpolate at this gm/Id; else return full curve",
    )
    parser.add_argument(
        "--corner", type=str, default="tt",
        help="Process corner: tt, ff, ss, fs, sf (default: tt)",
    )
    parser.add_argument(
        "--temp", type=str, default="25C",
        help="Temperature: -40C, 25C, 85C (reference temps; others are "
             "interpolated). Default: 25C.",
    )
    args = parser.parse_args()

    _UNITS = {
        "id_w":  "A/m",
        "gm_gds": "V/V",
        "gm_id":  "1/V",
        "cgg_w": "F/m",
        "cgd_w": "F/m",
        "cgs_w": "F/m",
        "cdb_w": "F/m",
        "ft":    "Hz",
        "vgs":   "V",
        "vth":   "V",
        "vdsat": "V",
    }
    unit = _UNITS.get(args.metric, "")

    def _query_one(l_val: float) -> dict:
        try:
            result = lut_query(
                args.device, args.metric, l_val,
                corner=args.corner, temp=args.temp,
                gm_id_val=args.gm_id,
            )
            if args.gm_id is not None:
                return {"L_um": l_val, "value": float(result), "unit": unit, "status": "ok"}
            else:
                return {
                    "L_um": l_val,
                    "curve": result[["gm_id", args.metric]].to_dict(orient="records"),
                    "unit": unit,
                    "status": "ok",
                }
        except FileNotFoundError as e:
            return {"L_um": l_val, "status": "lut_not_found", "message": str(e)}
        except (ValueError, KeyError) as e:
            return {"L_um": l_val, "status": "error", "message": str(e)}

    rows = [_query_one(l) for l in args.L]

    if len(rows) == 1:
        out = rows[0]
    else:
        out = {"results": rows}

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    _cli_main()
