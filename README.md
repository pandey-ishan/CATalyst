# CATalyst

A Windows desktop prototype for reviewing test provider CAT mocks. It captures QA questions locally while you browse, lets you correct extracted details, and tracks overall plus sectional scores and percentiles.

## Run

Dependencies are installed in this project's `.venv`. Double-click **Start-CAT-Analyst.bat**, or run from PowerShell:

```powershell
.\.venv\Scripts\python.exe -m cat_analyst
```

For a fresh installation (Windows, Python 3.11):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m cat_analyst
```

Installation downloads packages and bundled OCR models. Normal app operation uses local processing, with no cloud API, account, or remote OCR service.

## Review a mock

1. Open test provider post-test review on your **primary display**, on the QA section.
2. Click **New recording**. Optional screenshot retention is off by default.
3. Drag a rectangle around the question and review panel. Include the question number such as `01/22`, the question/options, and the review tabs. Keep the recording notch outside this rectangle.
4. Return focus to test provider. Browse each QA question, including unattempted questions, and display both **Statistics** and **Text Solution**. Hold each view steady until the toolbar reports it captured the view. The app samples at 2 frames per second and processes stable views in a background OCR worker.
5. Use **Pause / Resume** whenever needed. Pausing stops new recording frames and capture. Returning to the CATalyst editor also suspends new frame acquisition while its window has focus; click test provider again to continue.
6. Open **Review**, then **View question** (or double-click a row) for a readable question view without ending recording. Use the text-size control, previous/next, answer reveal, bookmark, and edit controls. You can correct topics, answers, difficulty, attempts, correctness, and time; manually edited fields are protected against subsequent OCR. Add missing questions manually if needed.
The top recording notch collapses after four seconds, keeping pause/resume and Review accessible. Click **More** to expand it.

7. Click **Stop & save**, enter a paper name, test date (defaults to today), all four scores and all four percentiles, and check the expected question count. Incomplete papers require an explicit acknowledgment so partial analysis is not presented as complete coverage.
8. After the database save succeeds, temporary recordings and capture files are deleted. If you cancel saving or saving fails, the draft and recording remain available through **Recover / review draft**. Recovered drafts can be edited, saved, or resumed with a newly selected capture area.

Saved questions are in **Papers**. Open a question to bookmark it; it then appears under **Bookmarks**. The dashboard shows score trends and QA topic accuracy, attempts, and time analysis. Percentiles for every section are visible in paper details.

## Local data and privacy

The default data location is `%LOCALAPPDATA%\CATAnalyst`, outside this project's OneDrive directory:

- `analyst.sqlite3`: papers, text, scores, percentiles, bookmarks, and optional screenshot blobs.
- `sessions/<id>/draft.json`: autosaved unfinished questions and session state.
- `sessions/<id>/recording-*.avi`: temporary MJPEG recordings, until successful saving.
- Optional screenshots are temporary PNGs in the session folder, then embedded in SQLite at save.

Set `CAT_ANALYST_DATA` before launching to choose another local directory. Avoid a synced directory if you want to prevent your backup/sync software from uploading the data. The application itself does not upload data. Saved text and recordings are not encrypted. To back up, close the app and copy the data directory.

Only the selected screen rectangle is recorded, but whatever is visible there can be recorded. Pause before switching to unrelated content. Screenshots are not retained by default; the temporary video is still required by the recording workflow.

## Current limitations

- This is a first working prototype, not yet validated against your live test provider account. Tests use generated test provider-style text/screenshots based on the examples supplied.
- Capture selection currently supports the primary monitor. The capture rectangle remains fixed; reselect it by stopping and resuming the retained draft if the browser moves.
- The question number must be visible in each extracted view. If scrolling hides it, capture waits rather than guessing the question identity. Zoom out enough to show both the number and review content, or fill missing content manually. Arbitrary long-page scrolling needs further work.
- OCR is not guaranteed exact for equations, fractions, superscripts, option markers, or densely formatted content. Numeric-response and green-tick multiple-choice correct answers are supported. Include the tick at the right of the option in your capture area. A tick is the answer key, not evidence of your selection; selected multiple-choice answers may need manual entry. test provider Skipped is recorded as unattempted. Diagrams and video solutions are outside scope.
- Topic suggestions use local keyword rules and should be checked. Screen transitions faster than OCR can finish may be missed; review the coverage summary before saving.
- Statistics and Text Solution must be opened by you. The app does not control the test provider website or infer hidden fields. Navigate only QA questions during a session.
- Accuracy is correct / graded attempted questions. Unattempted questions do not count as incorrect; unknown results and times are excluded and coverage is displayed. Time analysis describes QA mock time, not time spent reviewing or recording.
- There is no installer or cloud sync. The launcher uses this project's virtual environment.

## If Review stays empty

A visible question number on the browser must also be inside the selected recording area. An early version selected the primary screen but recorded a secondary screen when Windows enumerated that display first; this is fixed. After updating, stop the old recording, cancel saving if no questions were captured, close/relaunch the app, and choose a new recording area. A running Python process does not reload code changes automatically.

Keep the browser on the primary screen and return focus to test provider after using the controls. If capture still waits for a question number, verify the selected rectangle contains the counter and question text.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tests.ocr_smoke
.\.venv\Scripts\python.exe -m pip check
```

The regression suite covers two-tab merging, user versus peer statistics, edit protection, whitespace duplicates, unattempted handling, analytics, transaction rollback, draft recovery, screenshot opt-in, video cleanup after save, GUI editing, pause/resume, stale OCR suppression, final-frame draining, and a playable generated recording. The OCR smoke check blocks socket connections and uses generated numeric-response and green-tick MCQ screenshots; it does not read your screen. Artifacts are written under `_test_artifacts/`.

## Project files

- `cat_analyst/core.py`: data model, merging, analysis, SQLite, and drafts.
- `cat_analyst/parser.py`: spatial test provider OCR parsing and topic suggestions.
- `cat_analyst/choice_marks.py`: local visual extraction of green tick-marked MCQ answers.
- `cat_analyst/display.py`: primary-monitor identification and scaled selection coordinates.
- `cat_analyst/capture.py`: recording, stable-view detection, and background local OCR.
- `cat_analyst/ui.py`: desktop UI, live review, paper saving, dashboard, and recovery.
- `QA.md` and `app-context.md`: decisions and current project state; review at session start.

Implementation references: [Qt thread and signal guidance](https://doc.qt.io/qtforpython-6.10/overviews/qtdoc-threads-qobject.html) and the installed RapidOCR package's bundled configuration/models. UI updates are delivered through Qt signals from the recording worker.

## Updated dashboard and question reader

The charcoal-and-gold overview includes weakest topics by accuracy, slowest topics by average attempted-question time, bookmarks, easy misses, extraction-review counts, accuracy/attempt progress bars, time spent on incorrect answers, and score trends. Topic ranking cards require at least three eligible observations and open those questions for review.

The side calendar highlights saved test dates. Select a date to open a paper. Its in-app reminder appears after **more than two days** since the latest test; it updates while the app is open. Dates and greetings use Asia/Calcutta. Older papers inherit their original creation date until a new date is supplied when saving.

In **Papers**, use **Delete question** or **Delete test**. Each asks for confirmation; deleting a test removes its questions and saved screenshots. Removing one question preserves the expected count so coverage stays honest.

Local OCR now uses raised-character geometry to recover simple exponents. The reader renders `x^{2}`, `x^(n+1)`, and `(0.125)^{-80}` as superscripts. Check the recovered expression: this is not a general mathematical OCR engine, and fractions or complex layouts may still need editing. Existing saved text is not automatically reprocessed; recapture or edit it.

Additional validation: `python -m tests.math_smoke` checks the installed OCR engine against a generated exponent image. `python -m tests.render_previews` produces synthetic dashboard/reader previews. The current regression suite has 47 tests, including dates, migration, deletion, calendar reminders, readers, rankings, and notch controls. No real user data is used by these tests.

Repeated captures are merged per question number, including small OCR variations and overlapping scroll text. With review tabs offscreen, recognizable explanations are stored as solutions; unclear fragments stay in Raw captured text with a warning. Keep the counter near the upper-left of the selected region. Existing repeated/incorrectly classified saved text is not rewritten automatically; edit it in Review. The regression suite now contains 54 tests.

The main window now opens within the available primary-screen area and centers itself. Cards reflow on resize; use vertical scrolling for lower dashboard sections. Navigation and recording controls use local vector line icons. The current regression suite has 56 tests, including startup geometry and narrower window layouts.

## Notebook interface

The current design uses cream paper, ink text and sage accents, superseding the earlier dark/gold appearance. Papers, questions, live Review, bookmarks and topic breakdowns use rounded entries rather than table grids. Select an entry to use its actions; double-click or press Enter to open question review. Long entry details wrap as the window narrows. All data and recording behavior remain local. The regression suite now contains 58 tests.

Current visual refinement: cream/light-blue surfaces with orange accents, a compact icon-only sidebar (hover for labels), and readable comparison tables. Rounded badges highlight scores, difficulty, results and times; percentage cells include progress bars. This supersedes the preceding all-list/sage design. Tables support row selection, double-click or Enter to review, and tooltips for clipped values. The regression suite now contains 60 tests.

Latest refinements: beige background, per-row View/Edit/Delete icons (including test metadata editing), a continuous rounded header, and calendar date hover details with scores/percentiles. The top notch expands on hover and compacts four seconds after leaving. Blue-filled MCQ options receive local contrast normalization; original pixels still determine green answer ticks. Selected MCQ answers remain manually editable. Current regression count: 65 tests; offline numeric and MCQ OCR smoke checks pass.
