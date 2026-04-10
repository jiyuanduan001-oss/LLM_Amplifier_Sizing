from CircuitCollector.runner.mosfet_lut_runner import MosfetLUTRunner

runner = MosfetLUTRunner("CircuitCollector/circuits/mosfet/nfet_01v8/interface.toml")
result = runner.run()