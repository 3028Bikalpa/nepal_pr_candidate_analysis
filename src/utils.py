"""
Utilities for parsing PR candidate PDF and producing analysis-ready datasets.

The PDF is text-based but uses embedded fonts that sometimes appear as (cid:###) in extracted text.
We remove those patterns and normalize key categorical fields.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
import pandas as pd
import pdfplumber

CID_RE = re.compile(r"\(cid:\d+\)")
SPACE_RE = re.compile(r"\s+")

# Party header pattern in the PDF
PARTY_RE = re.compile(r"राजनीितक दलको नाम:-\s*(.+)$")

def clean_line(s: str) -> str:
    """Remove (cid:###) sequences, checkmark glyphs, and normalize whitespace."""
    if s is None:
        return ""
    s = CID_RE.sub("", s)
    # common checkmark / bullets
    s = s.replace("\uf0fc", "").replace("\uf0fb", "").replace("\uf0fd", "")
    s = SPACE_RE.sub(" ", s).strip()
    return s

def normalize_gender(raw: str) -> str:
    """
    Normalize gender to Nepali: 'पुरुष' or 'महिला'
    PDF variants may look like: 'पुष', 'पु ष', 'म(हि)ला' etc. After cleaning we often see 'पुष' / 'महला'.
    """
    t = (raw or "").strip().lower()
    if any(k in t for k in ["female", "मह", "महि", "महला", "महिला"]):
        return "महिला"
    if any(k in t for k in ["male", "पु", "पुर", "पुष", "पुरुष"]):
        return "पुरुष"
    return (raw or "").strip()

def normalize_group(raw: str) -> str:
    """
    Normalize inclusive group (समावेशी समूह) to a small canonical set.
    The PDF typically contains:
      - आदिवासी जनजाति
      - खस आर्य
      - मधेशी
      - दलित
      - थारु
      - मुस्लिम
    """
    t = (raw or "").strip().lower()
    if ("आद" in t) or ("जनजात" in t):
        return "आदिवासी जनजाति"
    if ("खस" in t) or ("आर्य" in t) or ("आय" in t):
        return "खस आर्य"
    if ("मधेश" in t) or ("मधे" in t):
        return "मधेशी"
    if "दलित" in t:
        return "दलित"
    if ("थारु" in t) or ("था" in t and "रु" in t):
        return "थारु"
    if ("मुस" in t) or ("mus" in t):
        return "मुस्लिम"
    return (raw or "").strip()

def slugify(s: str) -> str:
    """Safe filename slug."""
    s = (s or "unknown").strip()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s)
    s = s.strip("_")
    return s[:120] if len(s) > 120 else s

def parse_candidate_rows_from_text_lines(lines: Iterable[str], current_party: Optional[str]) -> Tuple[List[Dict], Optional[str]]:
    """
    Parse cleaned text lines from a page into candidate rows.
    Returns (rows, updated_current_party).
    """
    rows: List[Dict] = []
    for raw in lines:
        line = clean_line(raw)
        if not line:
            continue

        m = PARTY_RE.search(line)
        if m:
            current_party = m.group(1).strip()
            continue

        # Data rows start with serial number (Arabic digits) followed by a space.
        if not re.match(r"^\d+\s", line):
            continue

        tokens = line.split(" ")
        try:
            serial = int(tokens[0])
        except Exception:
            continue

        # Find voter number: first all-digit token length >= 5
        voter_idx = None
        for i, tok in enumerate(tokens[1:], start=1):
            if re.fullmatch(r"\d{5,}", tok):
                voter_idx = i
                break
        if voter_idx is None or voter_idx + 1 >= len(tokens):
            continue

        voter_no = tokens[voter_idx]
        gender_raw = tokens[voter_idx + 1]
        gender = normalize_gender(gender_raw)

        name = " ".join(tokens[1:voter_idx]).strip()

        rest = tokens[voter_idx + 2:]
        # remove trailing checkmarks
        rest = [r for r in rest if r not in [""] and r.strip()]

        rest_str = " ".join(rest).strip()

        # Match inclusive group at the start (in the "cleaned" spelling)
        # Note: cleaning often removes some diacritics so we use simplified patterns.
        group = None
        district = None
        group_patterns = [
            ("आदवासी जनजात", "आदिवासी जनजाति"),
            ("खस आय", "खस आर्य"),
            ("मधेशी", "मधेशी"),
            ("दलित", "दलित"),
            ("था", "थारु"),
            ("मुस्लिम", "मुस्लिम"),
        ]
        for pat, norm in group_patterns:
            if rest_str.startswith(pat):
                group = norm
                district = rest_str[len(pat):].strip()
                break

        if group is None:
            # fallback: first token as group, remaining as district
            group = normalize_group(rest[0]) if rest else ""
            district = " ".join(rest[1:]).strip() if len(rest) > 1 else ""

        rows.append({
            "party": current_party,
            "serial": serial,
            "name": name,
            "voter_no": voter_no,
            "लिङ्ग": gender,
            "समावेशी समूह": group,
            "नागरिकता जारी जिल्ला": district,
        })

    return rows, current_party

def extract_candidates_from_pdf(pdf_path: str, max_pages: Optional[int] = None) -> pd.DataFrame:
    """Extract all candidate rows across the whole PDF."""
    all_rows: List[Dict] = []
    current_party: Optional[str] = None

    with pdfplumber.open(pdf_path) as pdf:
        pages = pdf.pages[:max_pages] if max_pages else pdf.pages
        for page in pages:
            text = page.extract_text() or ""
            page_rows, current_party = parse_candidate_rows_from_text_lines(
                text.splitlines(),
                current_party=current_party,
            )
            all_rows.extend(page_rows)

    df = pd.DataFrame(all_rows)
    # Basic cleanup
    df["party"] = df["party"].fillna("UNKNOWN_PARTY").astype(str).str.strip()
    df["नागरिकता जारी जिल्ला"] = df["नागरिकता जारी जिल्ला"].fillna("").astype(str).str.strip()
    df["समावेशी समूह"] = df["समावेशी समूह"].fillna("").astype(str).str.strip()
    df["लिङ्ग"] = df["लिङ्ग"].fillna("").astype(str).str.strip()
    return df
