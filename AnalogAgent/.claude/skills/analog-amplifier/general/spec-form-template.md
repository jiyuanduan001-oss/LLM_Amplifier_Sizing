# Design Spec Form

## Required (sizing will not proceed without these)
VDD          : 1.8         # Supply voltage (V)
CL           : 5e-12       # Load capacitance (F)
Gain         : 70          # DC gain target (dB)
GBW          : 60e6        # Gain-bandwidth product (Hz)
PM           : 60          # Phase margin (degrees)

## Environment (recommended — defaults applied if blank)
Temperature  : 40          # °C  (default: 27)
Corner       : ff          # tt, ff, ss, fs, sf  (default: tt)
VSS          : 0           # Ground reference (V)  (default: 0)

## Optional (leave blank to skip — will not be optimized)
Power        : 7e-4      # Max power (W)
SR+          : 30          # Positive slew rate (V/µs)
SR-          :             # Negative slew rate (V/µs)
CMRR         : 65          # (dB)
PSRR+        : 40          # Positive PSRR (dB)
PSRR-        : 60          # Negative PSRR (dB)
IRN          : 30e-6       # Integrated input-referred noise (V rms)
ORN          :             # Integrated output-referred noise (V rms)
Output_swing :             # (V)
I_bias       : 1e-5        # External bias current (A)

## Post-Sizing Options
Extreme_PVT  : yes          # yes/no — run additional sims at extreme corners
                            #   after sizing converges (SS/70°C + FF/0°C)
Optimize     : yes          # yes/no — run numerical optimization after sizing
                            #   converges. After the LLM sizing stage, the system
                            #   will ask which metric to prioritize: Power, Gain,
                            #   or GBW. The selected metric receives a higher
                            #   weight; the other two are still improved but with
                            #   lower priority. All other specs are kept above
                            #   user targets as constraints.
