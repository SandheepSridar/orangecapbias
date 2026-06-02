# Update Documentation

Regenerate `documentation.md` to reflect the current state of all SQL and Python scripts in the repo.

## When to use

Run `/update-docs` after:
- Adding a new script or SQL query
- Changing what a script reads or writes
- Changing key methodology (e.g. filters, thresholds)
- Adding or removing output files

## Steps

1. Read every script in the repo:
   - `src/parse_cricsheet.py`
   - `src/stats.py`
   - `src/visualize.py`
   - `src/analysis_queries.sql`
   - `app.py`

2. Read the current `documentation.md` to understand what already exists.

3. For each script, check whether the documentation accurately reflects:
   - What the script reads (inputs)
   - What it writes (outputs and file paths)
   - Key logic or decisions (filters, thresholds, methodology notes)
   - How to run it

4. Update only the sections that are stale or missing. Do not rewrite sections that are still accurate.

5. If a new script exists that has no documentation entry, add it following the same structure as existing entries.

6. Do not document implementation details that are obvious from reading the code. Focus on:
   - Non-obvious decisions (e.g. why wides are excluded, why 7+ match threshold)
   - Input/output file paths
   - How to run the script

## Rules

- Never delete an existing section unless the script it documents no longer exists
- Keep the Data Files table at the bottom up to date
- Match the formatting style of existing entries (headers, tables, code blocks)
- Do not add a timestamp or "last updated" line — git history serves that purpose
