@echo off
:: NeuronCLI — Run from anywhere on Windows
:: Usage:
::   neuron "add error handling to main.py"    (one-shot)
::   neuron                                     (interactive REPL)
::   neuron --provider ollama "explain this"    (use local Ollama)
::   neuron --dir C:\myproject "list all files" (specify working dir)

set "NEURON_ROOT=c:\RAHUL\PROJECTS _OF_Rahul\neuroncli"
set "PYTHONPATH=%NEURON_ROOT%;%PYTHONPATH%"
python -m neuroncli --dir "%CD%" %*
