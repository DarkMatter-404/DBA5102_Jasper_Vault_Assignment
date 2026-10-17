# Add this update to your existing branch

The ZIP contains a `jay/` tree. Upload the extracted files, not the ZIP itself. The main findings file is `jay/README.md`; new implementation and results are under `jay/revision_v3_2/`. Previous-version source dependencies are included so the bundle runs on its own. All packaged files belong under `jay/`.

## GitHub website

1. Extract the ZIP on your computer.
2. Open [the assignment repository](https://github.com/DarkMatter-404/DBA5102_Jasper_Vault_Assignment) and select your existing work branch using the branch selector.
3. Stay at the repository root. Choose **Add file → Upload files** and drag the extracted **jay folder** into the upload area. The resulting paths should start `jay/`; avoid creating `jay/jay/`.
4. Review the paths. This updates the main `jay/README.md` and adds V3.2; do not delete unrelated teammate files or older work.
5. Use the commit message: **Add combined PP pricing experiment with extended news and social validation**.
6. Commit to the selected existing branch. Use its existing open pull request to review the update; if that PR is already merged/closed, open a new comparison from this branch as appropriate.

The package is kept below GitHub's documented browser limits of 100 files per upload and 25 MiB per file. Market/training inputs are compressed inside the package so the complete market input fits the per-file limit. Keep those `.csv.gz` files compressed; the code reads them directly.

## Git command line alternative

Switch to your existing branch, then copy the extracted `jay` tree into the repository without removing other files. Replace `YOUR_EXISTING_BRANCH` with your actual branch name:

```bash
git switch YOUR_EXISTING_BRANCH
git status
# Copy the extracted jay folder here, merging directories.
git add jay/README.md jay/revision_v3_2
# If these dependencies are new to your branch, also stage their included paths:
git add jay/pp_pricing.py jay/revision_v2/pricing.py jay/revision_v3 jay/revision_v3_1
git diff --cached --stat
git commit -m "Add combined PP pricing experiment with extended news and social validation"
git push origin YOUR_EXISTING_BRANCH
```

Stage only this update's intended paths if your working tree contains other uncommitted edits. No commit, push or PR modification was performed in preparing this ZIP.

GitHub reference: [Adding a file to a repository](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository).
