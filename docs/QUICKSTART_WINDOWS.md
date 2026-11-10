# Run the demo on Windows (no Python needed)

1. Start **Docker Desktop** and wait until it says "Engine running".
2. Open the `data-align` folder in File Explorer.
3. Double-click **run-demo.bat**. The first run downloads a small Python image (about 1 minute).
4. A black window prints two lines: `clean migration: PASS` and `defective migration: FAIL`. Your browser then opens the report.

If double-click does nothing useful, open PowerShell in the folder and run:
`docker run --rm -v "${PWD}:/app" -w /app python:3.12-slim python -m dataalign demo --out dataalign_output`

(OneDrive folders sometimes block Docker file sharing. If you see a "mounts denied" error, copy the folder to `C:\data-align` and try again.)

Optional AI explanation: keep Ollama running, then add `--ai`. Inside Docker the engine must reach Ollama at
`http://host.docker.internal:11434`; set `OLLAMA_HOST` with `-e OLLAMA_HOST=http://host.docker.internal:11434`.
These last steps are not yet verified on a real Windows machine.
