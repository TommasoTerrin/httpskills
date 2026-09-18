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

Stato: domain layer e adapter layer (server MCP reale, auth a bearer token)
completi e testati; 39 criteri di accettazione coperti. Vedi la history del
progetto lanciata con `/lasagna official`.

## La cartella `skills/`

`skills/demo-skill/` è l'**unica skill di esempio** che il progetto spedisce
di suo: serve a dimostrare, con contenuto reale (frontmatter, un file in
`references/`, un file in `assets/`), che il server serve davvero ciò che
promette — non è un placeholder né un fixture di test isolato, viene servita
dal server quando lo avvii così com'è. Le skill vere le aggiunge chi opera il
server, fuori da questa feature: basta creare un'altra directory con un
`SKILL.md` valido sotto la stessa root (configurabile con la variabile
d'ambiente `HTTPSKILLS_SKILLS_ROOT`).

## Avviare il server

```bash
export HTTPSKILLS_SKILLS_ROOT="$(pwd)/skills"
export HTTPSKILLS_TOKENS="il-tuo-token"
uv run python -m httpskills
```

Espone `list_skills`, `get_skill` e `get_resource` su `http://127.0.0.1:8000/mcp`
(porta configurabile con `HTTPSKILLS_PORT`), protetti da bearer token.
