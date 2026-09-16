# httpskills

Server MCP HTTP (Python, [fastmcp](https://github.com/jlowin/fastmcp)) che espone una
libreria di [Agent Skills](https://agentskill.io) centralizzata e aggiornabile via
bearer token, replicando fedelmente il protocollo (progressive disclosure: frontmatter
sempre visibili, corpo caricato su richiesta).

Costruito con [lasagna](https://github.com/TommasoTerrin/lasagna-code) — questo repo
dichiara il plugin in `.claude/settings.json`, non lo vendorizza:

```bash
claude plugin install lasagna@lasagna
```

Stato: in avvio, spec non ancora scritta. Vedi `/lasagna official` nella history del
progetto una volta partito il primo ciclo.
