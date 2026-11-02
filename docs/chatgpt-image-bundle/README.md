# ChatGPT context bundle for the report figures

This prepares files for a **new ChatGPT Project**, not a separate image-generation application. It keeps the report's sixteen figure slots, provides figure-specific prompts and original evidence, and leaves image insertion into Word to the user. It does not generate the final figures, change the report, start containers or run experiments.

**Snapshot status, 2 November 2026:** these bundle templates describe the report before figure insertion. The current Word report now contains all sixteen figures. The original package remains a historical handoff; refresh the figure catalog, context and document verification record before building a new package from the illustrated report. The existing validation intentionally rejects an unmatched report instead of exporting stale instructions.

## Build the downloadable package

From the repository root, with Python 3.10 or newer:

```powershell
python ./scripts/build-chatgpt-image-bundle.py
```

The script uses the Python standard library and Git; it needs no API key, Docker connection or network. It prints a new build folder under `.runtime/chatgpt-image-bundle/`, containing the extracted package, **cloud-lab1-chatgpt-image-context.zip**, and the archive verification result. Each build gets a new directory so earlier packages are preserved.

Verify any delivered ZIP independently:

```powershell
python ./scripts/build-chatgpt-image-bundle.py --verify PATH_TO_ZIP
```

The extracted package also contains the verifier in `source/scripts/`. From its root, run `python ./source/scripts/build-chatgpt-image-bundle.py --verify PATH_TO_ZIP`; this verification mode does not need the original repository, Git or network access.

Source templates and the original three style images live here. The package includes a snapshot of the current working files, the Git revision and dirty-state information, and per-file hashes. It includes the complete current report and excludes earlier Word drafts, local credentials, runtime state, IDE settings and temporary files. No source file is modified by building.

## Initial uploads — five files

Extract the ZIP on your computer. Open its `START_HERE.md`, then upload these files to the new Project's Sources:

1. `01_PROJECT_CONTEXT.md` — the full handoff, figure briefs, prompts, verified tables, source/configuration appendix and document text.
2. `Raporti_Projektit_Monitorimi_i_Burimeve_Plote.docx` — the unchanged Albanian report.
3. `style-reference-01.png`.
4. `style-reference-02.png`.
5. `style-reference-03.png`.

Paste `PROJECT_INSTRUCTIONS.md` into the Project instructions and paste `OPENING_PROMPT.md` into its first chat. These two prompt files do not need additional Project upload slots. The ZIP is a transport format: do not assume that uploading the ZIP alone indexes its contents. No subscription-specific file allowance is assumed; use the attachments permitted by your account.

The official [Projects and chats guide](https://learn.chatgpt.com/docs/projects) explains shared uploaded sources and Project instructions. The new chat has no automatic access to this conversation, your local folders, or a running laboratory.

## Request a figure

Ask for one numbered figure at a time. Use its prompt in `FIGURE_CATALOG.md`; attach the original files listed in that entry from the package's `source/` folder. For example, Figure 13 uses the archived CPU plot, run record and measurement matrix. Figure 4 needs a real local container capture; it cannot be reconstructed as evidence by an image generator.

The three water-monitoring images are **style references only**. Their Kafka, Spark, Cassandra, sensor, email and Telegram components do not describe this application. The correct architecture and the permitted contents of each figure are supplied explicitly.

Screenshots retain their original UI and dates. Charts retain measured values and run identities. Diagrams can adopt the supplied white-background style. The future chat should return PNG files, the exact Albanian captions and placement instructions; it must not modify Word automatically.

## Authoring and refresh

- `context.md` explains the implemented system and the limits of the evidence.
- `figures.json` is the sixteen-entry brief catalog. Captions, sources and placeholder heights are checked against the report and chapter sources.
- `project-instructions.md`, `opening-prompt.md` and `style-guide.md` control the handoff workflow.
- `style-references/` contains unmodified copies of the three user-supplied images.

If the Word report changes, render/check it and update its document verification record before rebuilding; the packager refuses a report whose hash no longer matches that record. If application settings or figure captions change, reconcile these authoring files instead of silently exporting stale instructions. The packager cross-checks current settings and saved evidence, and records the exact inputs it used.

The report used for the original package was text-complete, with cover identity/logo fields and sixteen image placeholders. The current repository report has those figures inserted; the cover fields remain. A university logo is not generated by this bundle. Inserting or replacing images can change pagination; update fields and review the resulting Word document afterward.
