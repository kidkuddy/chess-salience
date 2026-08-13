# Gemini run status

The independent-vendor protocol was frozen in commit `7c01f56`. The subsequent one-item
probe did not reach the model and collected no label. Gemini CLI exited with code 41
because the local installation selected Vertex AI authentication but the process had no
`GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` or express-mode API key.

The complete failed probe record is retained in `data/gemini_labels_probe.jsonl`. No
prompt, gate, or analysis was changed after the failure. Once Google credentials are
configured, the intended commands remain:

```sh
python run_gemini_labels.py --probe --concurrency 1
python run_gemini_labels.py --concurrency 4
python score_gemini_labels.py
```

The first failed probe must remain in the probe file. A later successful probe is appended,
not substituted. The full output file is separate and does not yet exist.
