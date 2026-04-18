@echo off
:: NeuronCLI — Run from anywhere on Windows
:: Usage:
::   neuron "add error handling to main.py"    (one-shot)
::   neuron                                     (interactive REPL)
::   neuron --model llama3.2:3b "explain this"  (use specific model)
::   neuron --dir C:\myproject "list all files"  (specify working dir)

set "NEURON_ROOT=c:\RAHUL\PROJECTS _OF_Rahul\neuroncli"
pushd "%NEURON_ROOT%"
python -m neuroncli %*
popd
