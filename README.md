# Call Review Lab

Turn a pile of sales or customer calls into an account timeline, evidence checked observations, and a coaching report. Start with transcripts from any source. Calls without recordings stay in the timeline so gaps remain visible.

This public project is a fresh implementation of a private workflow. All accounts, speakers, quotes, and dates in `examples/` are invented. No customer data, CRM configuration, credentials, or private git history is included.

## Try it in two minutes

Requires Python 3.10 or newer. The core workflow uses only the standard library.

Clone the public repository, then run:

```bash
git clone https://github.com/rader-ai/sales-call-review.git
cd sales-call-review
python3 run.py demo
open workspace/report.html           # macOS
# xdg-open workspace/report.html     # Linux
```

The demo imports a synthetic discovery call, a later unrecorded meeting, and a sample analysis. It generates `workspace/report.html`, which is local and ignored by git. Run `python3 -m unittest discover -s tests` to check the core logic.

## Use it with your own calls

1. Obtain recordings or transcripts with permission. Redact sensitive material before using an external model.
2. Convert a transcript into Markdown turns: `**Speaker Name** [mm:ss] Spoken text`. Keep a raw original elsewhere and review diarization and timestamps before analysis.
3. Import a call:

```bash
python3 run.py init
python3 run.py add \
  --account "Example Account" --id "discovery-01" \
  --date "2026-01-12" --title "Discovery" \
  --internal "Rep Name" --external "Buyer Name" \
  --transcript /path/to/reviewed-transcript.md
python3 run.py report
```

For many calls, use `python3 run.py import-csv /path/to/calls.csv`. The CSV columns are `account,id,date,title,internal,external,transcript,recorded,source`. Transcript paths are relative to the CSV. Omit a transcript path to retain an unrecorded or missing call in the timeline. In CSV rows, separate multiple people in `internal` and `external` with semicolons. For `add`, separate names with commas. Account and call IDs are converted to folder safe slugs. Use unique IDs per account. `--replace` overwrites an imported call's transcript and metadata.

4. Review the measured statistics with `python3 run.py review`. The calculation counts words and question marks from the labeled transcript. Unknown speakers are excluded from talk share. A question mark count is not a measure of good discovery.
5. For qualitative analysis, use [the analyst prompt](prompts/analyze_call.md) with the reviewed transcript, `meta.json`, and any earlier analyses for that account. Save the result as `workspace/accounts/<account>/calls/<id>/analysis.json`. A blank shape is in `examples/analysis-template.json`. Tag repeated demand or competitive themes, and set a practice behavior and check in when the evidence supports it.
6. Run `python3 run.py report`. Every quote in the analysis is checked against a single speaker turn. Unsupported quotes are flagged and hidden from the visible evidence. Review the report with the account owner before using it for coaching. Repeat after training to see whether observed behavior changes.

## Optional local transcription

Install `ffmpeg` and [whisper.cpp](https://github.com/ggml-org/whisper.cpp) separately, put a compatible model on your computer, then run:

```bash
python3 run.py transcribe --media /path/to/call.mp4 \
  --model /path/to/ggml-model.bin \
  --output /path/to/call.txt --language en --threads 4
```

This only creates a raw text transcript. It does not identify speakers. Correct the text and create the Markdown turns before import. The original media is preserved. The model file and media stay out of git.

## What the method does

| Stage | Purpose | Output |
| --- | --- | --- |
| Timeline | Group calls by account and include missing recordings | Call coverage |
| Transcript review | Correct errors and label speakers without changing meaning | Auditable text |
| Deterministic measures | Count words, question marks, and longest internal run | `metrics.json` |
| Evidence based analysis | Ask what worked, what to practice, and what is still unknown | `analysis.json` |
| Quote verification | Check each quote within one speaker turn | `verification.json` |
| Cross account synthesis | Count themes by distinct account; read the evidence | Hypotheses for human review |
| Owner review | Reconcile the call with deal context and outcomes | Human coaching decisions |
| Recheck | Review later calls against selected coaching goals | Evidence of change |

The full private workflow also used CRM associations, demand and competitive themes, skeptical review of cross account findings, and customized training drills. This starter exposes the portable foundation. It does not silently infer deal outcomes, automatically fetch CRM data, or automate model analysis. The [method guide](docs/METHOD.md) describes how to extend it without confusing inference with observation.

## Privacy and deployment

The Python commands run locally and make no model API calls. The optional `whisper.cpp` path also runs locally after you install it. If you paste transcripts into a cloud coding agent or model, that provider processes the content under its own terms. Use appropriate consent, retention settings, redaction, and organizational policy. `workspace/`, media, models, and local configuration are ignored, but a git ignore rule is not access control. Review every staged file before publishing. Reports contain call content and belong in an access controlled location.

No HubSpot account or API key is needed. To connect a CRM later, export the small CSV interface or build a separate adapter with least privilege. Never put tokens, portal identifiers, real transcripts, or customer names in this repository.

## Credits

The original workflow drew on ACE and SPICED from Winning by Design and BANT from IBM. This starter does not implement or claim ownership of those frameworks. See [method guide](docs/METHOD.md) for a neutral rubric you can adapt to your own organization.

MIT licensed. Created by Chris Rader.
