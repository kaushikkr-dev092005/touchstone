# Captioned operator demo

The final local recording shows saved measured proofs and new simulated dashboard
actions with explicit labels. It sends no financial transaction or hosted inference.

Repository assets: [captioned WebM](recordings/touchstone-demo.webm) and
[transcript](recordings/demo-transcript.md). These are reviewable recording files;
they are not a portal upload or confirmed entry submission.

```text
python tools/check_release_browser.py --include-landing --record-demo --output tmp/final-live-demo-20261110
```

Outputs: `touchstone-demo.webm`, `demo-transcript.md` and `review.json`. The release
package includes the recording/transcript. It has captions and no audio; the
signed-in portal must confirm whether narration, a public video URL or another
format/length is required. A local file is not an uploaded submission.

| Scene | Demonstration |
|---|---|
| Saved Metal proof | Paid rejected answer and receipt replay without another purchase |
| Qualification and closure | Sonnet 120/120 calibration, 59/60 holdout; integrated USD 1 hold / USD 0.01 capture; separate 0.01 USDZ service charge |
| Comparison boundary | Clearing refusals and credit-cap stop, incomplete study, no savings claim |
| Signed fault | Current seller rejected credit; acknowledgement is not refund |
| Tools and review | Deterministic supported cases, unfamiliar roles require review |
| Three-job scenario | SIMULATED short float, halt/resume, immutable limits |
| Transaction inspection | Failed calls retain costs; quote/reservation/charge stay distinct |
| Closure and audit | SIMULATED captures/releases and complete receipt history |

Rehearse with `python tools/run_mock.py`, open http://127.0.0.1:8088. Never reuse
consumed approvals while filming. GPU inference is unnecessary for this recording.
See [the final measured review](LIVE_PROOFS_20261110.md) for precise limits.
