# Publish on GitHub: no coding, no installs

## 1. Make an account
1. Go to github.com and click Sign up. Use your email, make a username (this becomes part of your public link), verify your email.

## 2. Check what you are about to publish
- Open the data-align folder (the one that contains docker-compose.yml).
- Do NOT upload the .zip file. Upload the files and folders INSIDE the folder.
- The demo database password in docker-compose.yml is for local testing only. That is fine to publish.
- Never upload real company data, real passwords, or a Langflow export that contains keys.

## 3. Create the repository
1. Click the + icon (top right), then New repository.
2. Repository name: data-align
3. Description: Open-source AI-assisted data migration auditor
4. Choose Public.
5. Do NOT tick "Add a README" (we already have one).
6. Click Create repository.

## 4. Upload your files
1. On the new empty page, click the link "uploading an existing file".
2. Open the data-align folder in File Explorer. Press Ctrl + A to select everything inside it.
3. Drag it all into the GitHub upload box in your browser. Wait until every file shows as uploaded.
4. Scroll down. In the first box, type: Initial release. Leave "Commit directly to the main branch" selected.
5. Click Commit changes.

## 5. Check it
- Your README should appear under the file list.
- Click the folders (docs, sql, prompts, templates, test-data) and confirm they are there.
- If .gitignore is missing, that is OK for now.
- Click the **Actions** tab. A workflow called "tests" should start by itself and turn green in about a minute. If the
  `.github` folder did not upload (Windows hides it), click Add file > Upload files and drag the `.github` folder in, or turn on
  View > Show > Hidden items in File Explorer and repeat step 4.
- Replace YOUR-USERNAME in README.md with your real GitHub username (pencil icon > edit > commit) so the green badge works.

## 6. Fix the placeholder
1. Click README.md, then the pencil icon (Edit).
2. Replace YOUR-USERNAME with your GitHub username. Click Commit changes.

## 7. Make it look professional
1. On the main page, click the gear icon next to About.
2. Add topics: data-migration, data-quality, langflow, ollama, open-source, qa-testing.
3. Click Save changes.

## 8. Add the flow file (after your flow works)
1. In Langflow, export your flow (choose the option without API keys).
2. Open the file in Notepad and search for "password" and "key". Remove anything real.
3. On GitHub click Add file, then Upload files, drag the file in, and commit.

## 9. First release
1. Click Releases on the right, then Create a new release.
2. Tag: v0.1.0. Title: Data-Align v0.1.0. Describe what works and what does not.
3. Click Publish release.

## Updating later
Each time you improve something: Add file, Upload files, drag the changed files in (same names replace the old ones), Commit changes.
