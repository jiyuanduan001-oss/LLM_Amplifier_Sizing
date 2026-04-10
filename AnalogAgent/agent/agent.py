"""
AnalogAgent: LLM-guided analog circuit sizing agent using Anthropic Claude.

Loads the analog-amplifier skill stack, runs a tool-use conversation loop,
and saves reasoning traces. The LLM follows skill instructions to perform
all design calculations (via Python) and sizing decisions. Tools provide
LUT data access and CircuitCollector simulation.

Usage:
    from agent.agent import AnalogAgent

    agent = AnalogAgent()
    result = agent.run(
        task="Size a 5T OTA with GBW=10 MHz, A0=40 dB, CL=10 pF on SKY130.",
    )
"""

import json
import datetime
from pathlib import Path
from typing import Optional, Any

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

from scripts.lut_lookup import lut_query as _lut_query, list_available_L as _list_L

SKILLS_DIR = Path(__file__).parent.parent / ".claude" / "skills"
TRACES_DIR = Path(__file__).parent.parent / "traces"
TRACES_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# Skill helpers
# ---------------------------------------------------------------------------

def load_skill(skill_name: str) -> str:
    """Load a skill's SKILL.md by subdirectory name."""
    path = SKILLS_DIR / skill_name / "SKILL.md"
    if not path.exists():
        raise FileNotFoundError(f"Skill not found: {path}")
    return path.read_text()


def list_skills() -> list[str]:
    """Return all available skill names (subdirectory names)."""
    return [p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")]


# ---------------------------------------------------------------------------
# Trace helpers
# ---------------------------------------------------------------------------

def save_trace(task: str, reasoning: list[dict], result: dict) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    trace = {"timestamp": ts, "task": task, "reasoning": reasoning, "result": result}
    out = TRACES_DIR / f"trace_{ts}.json"
    out.write_text(json.dumps(trace, indent=2, default=str))
    return out


class TraceBuilder:
    """Accumulate reasoning steps during a sizing session, then save."""

    def __init__(self, task: str):
        self.task = task
        self.steps: list[dict] = []

    def thought(self, text: str):
        self.steps.append({"type": "thought", "content": text})

    def thinking(self, text: str):
        self.steps.append({"type": "thinking", "content": text})

    def tool_call(self, tool: str, inputs: dict, output: Any):
        self.steps.append({
            "type": "tool_call",
            "tool": tool,
            "inputs": inputs,
            "output": output if isinstance(output, (dict, list, str, int, float)) else str(output),
        })

    def finish(self, result: dict) -> Path:
        return save_trace(self.task, self.steps, result)


# ---------------------------------------------------------------------------
# Tool definitions for Claude API (topology-agnostic)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "lut_query",
        "description": (
            "Look up device characterization data from gm/Id LUT files. "
            "Returns the value of a given metric at a specific gm/Id operating point, "
            "or the full curve as a list of {gm_id, value} pairs if gm_id_val is omitted.\n"
            "Available devices: 'nfet', 'pfet' (SKY130 nfet_01v8, pfet_01v8).\n"
            "Available metrics: 'gm_id' (S/A), 'gm_gds' (V/V), 'id_w' (A/m = uA/um), "
            "'ft' (Hz), 'cgg_w' (F/m), 'cgd_w' (F/m), 'cgs_w' (F/m), 'vov' (V).\n"
            "Supports PVT corner and temperature selection."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device type: 'nfet' or 'pfet'",
                },
                "metric": {
                    "type": "string",
                    "description": "Metric to look up: 'gm_id', 'gm_gds', 'id_w', 'ft', 'cgg_w', 'cgd_w', 'cgs_w', 'vov'",
                },
                "L": {
                    "type": "number",
                    "description": "Channel length in micrometers (e.g., 0.18, 0.5, 1.0). Use list_available_L to see available values.",
                },
                "corner": {
                    "type": "string",
                    "description": "Process corner: 'tt', 'ff', 'ss', 'fs', 'sf' (default: 'tt')",
                },
                "temp": {
                    "type": "string",
                    "description": "Temperature: '0C', '25C', '75C' (default: '25C')",
                },
                "gm_id_val": {
                    "type": "number",
                    "description": (
                        "Optional: interpolate the metric at this gm/Id value (S/A). "
                        "If omitted, the full curve is returned."
                    ),
                },
            },
            "required": ["device", "metric", "L"],
        },
    },
    {
        "name": "list_available_L",
        "description": (
            "List all available channel lengths (in micrometers) for a given device, "
            "corner, and temperature. Use this to know which L values can be queried."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "Device type: 'nfet' or 'pfet'",
                },
                "corner": {
                    "type": "string",
                    "description": "Process corner (default: 'tt')",
                },
                "temp": {
                    "type": "string",
                    "description": "Temperature (default: '25C')",
                },
            },
            "required": ["device"],
        },
    },
    {
        "name": "convert_sizing",
        "description": (
            "Convert per-role sizing targets into CircuitCollector parameter dict. "
            "This translates gm/Id-space decisions (gm_id, L, Id per role) into "
            "the W/L ratio, finger count, and device params that CircuitCollector expects. "
            "Supports two topologies:\n"
            "  - '5t_ota': 4 roles (DIFF_PAIR, LOAD, TAIL, BIAS_REF) → 5tota\n"
            "  - 'twostage': 6 roles (DIFF_PAIR, LOAD, BIAS_GEN, TAIL, OUTPUT_CS, OUTPUT_BIAS) → tsm\n"
            "Each role needs: gm_id_target (S/A), L_guidance_um (µm), id_derived (A). "
            "The tool uses LUT data to compute W from (gm_id, L, Id), then applies "
            "WL_ratio constraints and finger multiplier logic. "
            "For twostage topology, also provide Cc_f (compensation cap in F) and Ib_a (bias current in A)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topology": {
                    "type": "string",
                    "description": "Circuit topology: '5t_ota' or 'twostage'",
                },
                "roles": {
                    "type": "object",
                    "description": (
                        "Dict of role_name -> {gm_id_target, L_guidance_um, id_derived}. "
                        "Example for 5T OTA: "
                        '{"DIFF_PAIR": {"gm_id_target": 12.0, "L_guidance_um": 1.08, "id_derived": 5e-5}, '
                        '"LOAD": {"gm_id_target": 12.0, "L_guidance_um": 1.08, "id_derived": 5e-5}, '
                        '"TAIL": {"gm_id_target": 11.0, "L_guidance_um": 1.08, "id_derived": 1e-4}, '
                        '"BIAS_REF": {"gm_id_target": 0, "L_guidance_um": 1.08, "id_derived": 1e-5}}'
                    ),
                },
                "Ib_a": {
                    "type": "number",
                    "description": "Bias current in Amperes. Required for 5t_ota (sets ibias param) and twostage.",
                },
                "Cc_f": {
                    "type": "number",
                    "description": "Compensation capacitor in Farads (required for twostage topology only).",
                },
                "l_overrides": {
                    "type": "object",
                    "description": "Optional per-role L (µm) overrides, e.g. {\"DIFF_PAIR\": 2.0}",
                },
            },
            "required": ["topology", "roles", "Ib_a"],
        },
    },
    {
        "name": "simulate",
        "description": (
            "Run a SPICE simulation via CircuitCollector. "
            "Send a params dict (device sizes: {M1_L, M1_WL_ratio, M1_M, ...}) "
            "and a config path (e.g., 'config/skywater/opamp/5tota.toml' for 5T OTA, "
            "'config/skywater/opamp/tsm.toml' for two-stage Miller).\n"
            "Returns:\n"
            "  - specs: AC (dcgain_, gain_bandwidth_product_, phase_margin, cmrrdc, DCPSRp, DCPSRn), "
            "DC (power, vos25, tc), "
            "Noise (input_noise_density_1Hz, input_noise_density_spot, output_noise_density_1Hz, "
            "output_noise_density_spot, integrated_input_noise, integrated_output_noise), "
            "Slew rate (slew_rate_pos, slew_rate_neg), "
            "Output swing (vout_low, vout_high, output_swing)\n"
            "  - transistors: per-device OP data (gm, gds, id, vgs, vds, vth, region, cgg)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "params": {
                    "type": "object",
                    "description": (
                        "CircuitCollector parameter dict. Keys are device params like "
                        "'M1_L', 'M1_WL_ratio', 'M1_M', 'ibias', 'C1_value', etc."
                    ),
                },
                "config_path": {
                    "type": "string",
                    "description": (
                        "CircuitCollector TOML config path. "
                        "Examples: 'config/skywater/opamp/5tota.toml' (5T OTA), "
                        "'config/skywater/opamp/tsm.toml' (two-stage Miller)."
                    ),
                },
                "corner": {
                    "type": "string",
                    "description": "Process corner override: 'tt', 'ff', 'ss', 'fs', 'sf' (default: from TOML, typically 'tt')",
                },
                "temperature": {
                    "type": "number",
                    "description": "Simulation temperature in °C (default: 27)",
                },
                "supply_voltage": {
                    "type": "number",
                    "description": "Supply voltage override in V (default: from TOML, typically 1.8)",
                },
                "CL": {
                    "type": "number",
                    "description": "Load capacitance override in pF (default: from TOML)",
                },
                "spec_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Specs to extract. If omitted, all available specs are requested "
                        "(AC, DC, noise, slew rate, output swing). "
                        "Pass a subset to request only specific measurements."
                    ),
                },
            },
            "required": ["params", "config_path"],
        },
    },
    {
        "name": "check_server",
        "description": "Check if the CircuitCollector simulation server is running at localhost:8001.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------

_LUT_UNITS = {
    "gm_id": "S/A", "gm_gds": "V/V", "id_w": "A/m (=uA/um)",
    "ft": "Hz", "cgg_w": "F/m", "cgd_w": "F/m", "cgs_w": "F/m", "vov": "V",
}


def _execute_tool(name: str, inputs: dict) -> Any:
    """Dispatch a tool call from Claude to the actual Python implementation."""

    if name == "lut_query":
        device = inputs["device"]
        metric = inputs["metric"]
        L = float(inputs["L"])
        corner = inputs.get("corner", "tt")
        temp = inputs.get("temp", "25C")
        gm_id_val = inputs.get("gm_id_val")
        if gm_id_val is not None:
            gm_id_val = float(gm_id_val)

        try:
            result = _lut_query(device, metric, L, corner=corner, temp=temp, gm_id_val=gm_id_val)
            if gm_id_val is not None:
                return {"value": float(result), "unit": _LUT_UNITS.get(metric, ""), "status": "ok"}
            else:
                df = result
                return {
                    "curve": df[["gm_id", metric]].to_dict(orient="records"),
                    "unit": _LUT_UNITS.get(metric, ""),
                    "status": "ok",
                }
        except FileNotFoundError:
            return {
                "status": "lut_not_found",
                "message": f"LUT file not found for {device} L={L} um corner={corner} temp={temp}.",
            }
        except (ValueError, KeyError) as e:
            return {"status": "error", "message": str(e)}

    elif name == "list_available_L":
        device = inputs["device"]
        corner = inputs.get("corner", "tt")
        temp = inputs.get("temp", "25C")
        try:
            L_values = _list_L(device, corner=corner, temp=temp)
            return {"L_values_um": L_values, "count": len(L_values), "status": "ok"}
        except FileNotFoundError as e:
            return {"status": "error", "message": str(e)}

    elif name == "convert_sizing":
        from tools.param_converter import convert_sizing
        return convert_sizing(
            topology=inputs["topology"],
            roles_raw=inputs["roles"],
            Ib_a=float(inputs["Ib_a"]),
            Cc_f=float(inputs["Cc_f"]) if inputs.get("Cc_f") else None,
            l_overrides=inputs.get("l_overrides"),
        )

    elif name == "simulate":
        from tools.api_client import simulate as _simulate, check_server as _check
        from tools.bridge import parse_response, parse_specs

        if not _check():
            return {
                "status": "error",
                "message": "CircuitCollector server not reachable at http://localhost:8001.",
            }

        params = inputs["params"]
        config_path = inputs["config_path"]
        from tools.bridge import DEFAULT_SPEC_LIST
        spec_list = inputs.get("spec_list", DEFAULT_SPEC_LIST)

        # Merge PVT overrides into params (CircuitCollector routes them to correct TOML sections)
        for pvt_key in ("corner", "temperature", "supply_voltage", "CL"):
            if pvt_key in inputs:
                params[pvt_key] = inputs[pvt_key]

        try:
            response = _simulate(params=params, base_config_path=config_path, spec_list=spec_list)
            transistors = parse_response(response)
            specs = parse_specs(response)

            # Serialize TransistorOP objects to dicts
            transistors_out = {}
            for tname, t in transistors.items():
                transistors_out[tname] = {
                    "gm": t.gm, "gds": t.gds, "id": t.id,
                    "gm_id": t.gm / t.id if t.id > 0 else None,
                    "gm_gds": t.gm / t.gds if t.gds > 0 else None,
                    "vgs": t.vgs, "vds": t.vds, "vth": t.vth,
                    "region": t.region, "cgg": t.cgg,
                }

            return {"status": "ok", "specs": specs, "transistors": transistors_out}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    elif name == "check_server":
        from tools.api_client import check_server as _check
        ok = _check()
        return {"server_running": ok, "url": "http://localhost:8001"}

    else:
        return {"status": "error", "message": f"Unknown tool: {name}"}


# ---------------------------------------------------------------------------
# AnalogAgent
# ---------------------------------------------------------------------------

class AnalogAgent:
    """
    LLM-guided analog circuit sizing agent.

    Loads the analog-amplifier skill stack into the system prompt, then runs
    a tool-use conversation loop with Claude. The LLM performs all design
    reasoning and calculations (via Python) guided by the skills. Tools
    provide LUT data access and CircuitCollector simulation.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        self.model = model
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt from the analog-amplifier skill stack."""
        sections = [
            "You are AnalogAgent, an expert analog IC design assistant.\n\n"
            "You use gm/Id methodology to size analog circuits on SKY130. "
            "You have access to tools for LUT data lookup and SPICE simulation "
            "via CircuitCollector.\n\n"
            "IMPORTANT RULES:\n"
            "- Follow the skill instructions below for the design flow\n"
            "- You MUST use Python to compute ALL numerical results — never do mental math\n"
            "- Use lut_query to look up device data; use list_available_L to discover L values\n"
            "- Use simulate to run SPICE verification via CircuitCollector\n"
            "- Group output by circuit Role (topology-dependent)\n"
            "- Iterate: compare simulation results against specs, diagnose failures, adjust\n\n"
        ]

        # Load the analog-amplifier skill stack
        skill_name = "analog-amplifier"
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_path.exists():
            sections.append(f"---\n## SKILL: {skill_name}\n\n")
            sections.append(skill_path.read_text())
            sections.append("\n\n")
        else:
            sections.append(f"WARNING: Skill '{skill_name}' not found at {skill_path}\n\n")

        return "".join(sections)

    def run(
        self,
        task: str,
        max_turns: int = 30,
        save: bool = True,
        verbose: bool = True,
    ) -> dict:
        """
        Run the agent for a circuit sizing task.

        Args:
            task:       Natural language description of the sizing task,
                        including circuit topology, specs, and constraints.
            max_turns:  Maximum conversation turns (tool calls) before stopping.
            save:       Whether to save the trace to disk.
            verbose:    Print each thinking/text/tool step to terminal.

        Returns:
            {
              "final_message": str,
              "trace_path": str (if save=True),
              "steps": list[dict],
              "turns": int,
            }
        """
        trace = TraceBuilder(task)
        messages = [{"role": "user", "content": task}]

        if verbose:
            print(f"[AnalogAgent] Task: {task}")
            print("=" * 60)

        final_text = ""
        turn = 0

        while turn < max_turns:
            turn += 1

            if verbose:
                print(f"\n[Turn {turn}] Calling Claude...")

            response = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                thinking={"type": "enabled", "budget_tokens": 10000},
                system=self._system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )

            assistant_content = response.content
            text_parts = []
            tool_use_blocks = []

            for block in assistant_content:
                if block.type == "thinking":
                    trace.thinking(block.thinking)
                    if verbose:
                        preview = block.thinking[:200].replace("\n", " ")
                        print(f"  [thinking] {preview}...")
                elif block.type == "text":
                    text_parts.append(block.text)
                    trace.thought(block.text)
                    if verbose:
                        preview = block.text[:300].replace("\n", " ")
                        print(f"  [text] {preview}")
                elif block.type == "tool_use":
                    tool_use_blocks.append(block)

            if text_parts:
                final_text = "\n".join(text_parts)

            if response.stop_reason == "end_turn":
                if verbose:
                    print(f"\n[Turn {turn}] Done (end_turn).")
                break

            if not tool_use_blocks:
                break

            # Execute tool calls
            tool_results = []
            for block in tool_use_blocks:
                tool_name = block.name
                tool_inputs = block.input

                if verbose:
                    inputs_preview = json.dumps(tool_inputs, default=str)[:120]
                    print(f"  [tool] {tool_name}({inputs_preview})")

                tool_output = _execute_tool(tool_name, tool_inputs)
                trace.tool_call(tool_name, tool_inputs, tool_output)

                if verbose:
                    output_preview = json.dumps(tool_output, default=str)[:120]
                    print(f"    --> {output_preview}")

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(tool_output, default=str),
                })

            messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": tool_results})

        result = {
            "final_message": final_text,
            "steps": trace.steps,
            "turns": turn,
        }

        if save:
            trace_path = trace.finish(result)
            result["trace_path"] = str(trace_path)
            print(f"[AnalogAgent] Trace saved → {trace_path}")

        return result
