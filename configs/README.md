# Experiment arms

These two files are the single source of truth for the experiment arms.
`src/run_experiment.py` loads them directly into `ARMS`; nothing else differs
between the two arms.

| Arm | File | `max_debate_rounds` | Meaning |
|---|---|---:|---|
| baseline | `baseline.json` | 1 | upstream `DEFAULT_CONFIG` default |
| modified | `modified.json` | 3 | the one modification under study |

The modification is therefore reviewable as a two-line diff:

```diff
-  "max_debate_rounds": 1
+  "max_debate_rounds": 3
```

Everything else is held fixed: upstream commit `9fa1196`, the pinned synthetic
dataset, the scripted model class, seeds 0-4, the ticker/date grid, prompts,
tool schemas and the measurement code. See
`results/tables/experiment_audit.json` for a machine-readable record of the
config diff.
