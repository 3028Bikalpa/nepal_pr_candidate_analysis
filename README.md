# Nepal PR Candidate List Analysis (Proportional Candidates)

This project parses the Election Commission of Nepal PDF candidate lists (PR / समानुपातिक) and analyzes:
- **लिङ्ग** (Gender)
- **समावेशी समूह** (Inclusive Group)
- **नागरिकता जारी जिल्ला** (Citizenship-issuing district)

Outputs:
- `data/processed/candidates.csv` : extracted rows for all parties
- `outputs/figures/` : PNG charts (overall + per-party)
- `outputs/tables/` : CSV summary tables

## How to run
1. Create env and install deps:
   ```bash
   pip install -r requirements.txt
   ```
2. Open notebooks in order:
   - `notebooks/01_extract_clean.ipynb`
   - `notebooks/02_analysis.ipynb`

## Notes on language / encoding
The source PDF mixes Nepali and English. Extraction is text-based (not OCR), and some glyphs may lose diacritics during extraction.
We therefore **normalize** key categorical fields using robust rules.
