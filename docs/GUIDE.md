# Step-by-step guide

## Part 1: Install prerequisites
1. Install **Docker Desktop** (docker.com) or Docker Engine on Linux. Start it.
2. Install **Git** (git-scm.com). Check: `git --version`.
3. Hardware: 16 GB RAM minimum. An 8 GB GPU runs the 7B model well; for 12-16 GB VRAM you can try `qwen2.5:14b`.

## Part 2: Start the stack
Install Ollama on your computer (ollama.com), then:
```bash
ollama pull qwen2.5:7b
docker compose up -d
```
Services: Langflow :7860, Gotenberg :3000, demo Postgres :5432. Ollama runs on your computer at :11434.

## Part 3: Test the report template (no AI needed)
```bash
pip install jinja2 requests
python scripts/render_report.py test-data/sample_audit.json
```
Open `output/report.html` (and `report.pdf` if Gotenberg is up).

## Part 4: Build the flow in Langflow (http://localhost:7860)
Component names differ slightly between versions. Search the component panel for the closest match.

**Box 1: Data Picker**
1. Add four **SQL Database** components (or SQL Query): source profile, target profile,
   source sample, target sample.
2. Database URL for the demo (from inside Docker):
   `postgresql://demo:demo_password_change_me@postgres:5432/demo`
3. Paste queries from `sql/postgres_profile.sql`, replacing `{SCHEMA}`, `{TABLE}`, `{KEY}`
   (demo: legacy/cloud, customers, id). Queries 1-3 go into each *profile* component, query 4 into each *sample* component.
4. Add **Combine/Parser** components to package the results into
   source_profile, target_profile, source_sample, target_sample.

**Box 2: Smart Auditor**
1. Add a **Prompt** component. Paste `prompts/auditor_system_prompt.txt`. The `{{...}}` names become input handles; connect Box 1 outputs.
   For audit_id and timestamp, add simple text inputs.
2. Add an **Ollama** component: base URL `http://host.docker.internal:11434`, model `qwen2.5:7b`,
   temperature `0`, JSON format on.
3. **IMPORTANT:** set the context window (`num_ctx`) to at least 16384.
   Ollama's small default will silently truncate your profiles and give wrong results.
4. Connect Prompt -> Ollama.

**Box 3: Report**
1. Add a **Custom Component**, paste `langflow/render_component.py`. (Our compose file mounts
   `templates/` at `/app/templates` for it.)
2. Connect Ollama output -> its `audit_json` input.
3. Add an **API Request** component: POST `http://gotenberg:3000/forms/chromium/convert/html`,
   multipart file field `files`, filename `index.html`, content = rendered HTML.
   If this is awkward in your version, extend the custom component to call Gotenberg itself
   (see `html_to_pdf` in `scripts/render_report.py`).
4. Output -> Chat Output / file.

**Run it** with the Playground. Expected result on demo data: status FAIL with findings for
the dropped row, truncated email, and balance mismatch; phone_number mapped to primary_contact_cell;
date change recognized as a format change.

## Part 5: Judge your results
Run it 3-5 times. Check that all five defects are found every time, no numbers are invented,
and JSON is valid. If not: lower temperature, try a larger model, or tighten the prompt.

## Part 6: Export the flow safely
1. In Langflow, use Export on the flow, and choose the option **without API keys/credentials** if offered.
2. Save as `langflow-flow.json` in the repo root.
3. Open it in a text editor and search for `password`, `postgresql://`, `key`, `token`.
   Replace anything real with placeholders. A leaked password in a public repo is the biggest risk here.

## Part 7: Publish on GitHub
1. Create an account at github.com.
2. Click **New repository**: name `data-align`, Public, do NOT tick "add README" (we have one).
3. In a terminal inside the project folder:
```bash
git init
git add .
git status          # review the list: no passwords, no .env, no PDFs
git commit -m "Initial release of Data-Align"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/data-align.git
git push -u origin main
```
4. When asked to sign in, use a **Personal Access Token** (GitHub > Settings > Developer settings >
   Tokens) as the password, or install GitHub CLI and run `gh auth login`.
5. On the repo page, add a description and topics (`data-migration`, `langflow`, `ollama`, `data-quality`).
6. Create a **Release** (v0.1.0) and attach a sample PDF report.
7. Put a screenshot of the flow and the sample report at the top of the README.

## Part 8: After launch
- Enable GitHub Issues and Discussions.
- Add `good first issue` labels (MySQL SQL, new test defects, prompt improvements).
- Share it on relevant communities (Langflow Discord, r/dataengineering) once the demo works end to end.
