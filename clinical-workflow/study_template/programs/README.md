# Program chain boundary

`programs/` stores versioned source code artifacts for study execution chains.

Current POC policy:

- Python may be used as the executable reference/test chain and should emit CSV outputs for terminal inspection.
- R code remains a required traceable code artifact when applicable.
- SAS code is generated and tracked, but is not executed until a SAS runtime is explicitly configured.

Programs must not read unreviewed parser JSON directly.
