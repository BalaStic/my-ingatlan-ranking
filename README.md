# ingatlan ranking

Score and rank real estate listings (`main.py`) using configurable scoring weights and optional pre-filters.

## Quick start

```powershell
python main.py -i JSON/ingatlanok.json -c default
```

## CLI options

| Option | Alias | Required | Default | Description |
|---|---|---|---|---|
| `--input` | `-i` | **yes** | — | Input JSON file with property data |
| `--config` | `-c` | **yes** | — | Scoring config label from `JSON/scoring_config.json` |
| `--config-file` | — | no | `JSON/scoring_config.json` | Path to the scoring config JSON |
| `--prefilter` | `-p` | no | *(disabled)* | Prefilter config label from `JSON/prefilters.json` |
| `--enable-reranking` | — | no | *(off)* | Enable final re-ranking via `rankrules.py` |

## Output

Results are written to a folder named `ranked_{LABEL}/` (e.g. `ranked_default/`), containing:

| File | Description |
|---|---|
| `ranked_{LABEL}.txt` | Full text report (top-10 detail + full ranking) |
| `ranked_ingatlanok.json` | Top-10 properties as JSON |
| `scoring_config.json` | The scoring config used |
| `prefilter.json` | The prefilter config used (only if `-p` was given) |

The output folder is deleted and recreated on every run.

## PowerShell convenience

Source `variables.ps1` to load path variables into your terminal:

```powershell
. .\variables.ps1
python main.py -i $ingatlanok_json -c "modern first" -p "csak lakások 100-120M"