"""
Glossary handling module for Search Glossary.

Loads glossary CSVs and finds glossary terms inside pasted text.
Matching is deterministic — no AI, no fuzzy matching.
"""

import csv
import os
import re
import sys
import json
import logging
import platform
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# Version manifests. The bundled one ships next to the CSVs in the repo and
# is also what the updater reads from GitHub. The installed one is written
# by UpdateManager whenever it downloads a CSV into the user data dir.
BUNDLED_MANIFEST = "glossary-versions.json"
INSTALLED_MANIFEST = "installed-versions.json"

UNKNOWN_VERSION = "0.0.0"

# Typographic characters that Excel and Word substitute automatically, mapped
# back to the plain ASCII equivalents people actually type. Applied to both
# glossary terms and pasted text, so "d’oh!" in the CSV matches "d'oh!" typed
# by hand — and vice versa.
#
# Every mapping MUST be one character to one character. Matching relies on
# positions in the normalised text lining up with the original, so a mapping
# that changed the string length (e.g. "…" -> "...") would break it.
CHARACTER_EQUIVALENTS = {
    "\u2018": "'",   # ' left single quote
    "\u2019": "'",   # ' right single quote / typographic apostrophe
    "\u02bc": "'",   # ʼ modifier letter apostrophe
    "\u00b4": "'",   # ´ acute accent, sometimes typed as an apostrophe
    "\uff07": "'",   # ＇ fullwidth apostrophe
    "\u201c": '"',   # " left double quote
    "\u201d": '"',   # " right double quote
    "\uff02": '"',   # ＂ fullwidth quote
    "\u2010": "-",   # ‐ hyphen
    "\u2011": "-",   # ‑ non-breaking hyphen
    "\u2012": "-",   # ‒ figure dash
    "\u2013": "-",   # – en dash
    "\u2014": "-",   # — em dash
    "\u2212": "-",   # − minus sign
    "\uff0d": "-",   # － fullwidth hyphen-minus
    "\u00a0": " ",   #   non-breaking space (very common in web copy-paste)
    "\u2007": " ",   #   figure space
    "\u202f": " ",   #   narrow non-breaking space
    "\u3000": " ",   # 　 ideographic space, from Japanese input
}

# Fullwidth ASCII (Ａ-Ｚ, ａ-ｚ, ０-９, and punctuation) occupies U+FF01-FF5E,
# mapping one-to-one onto ASCII U+0021-007E. A Japanese IME produces these
# whenever it's in fullwidth mode, so "ＣＡＰ" typed in Japanese input would
# otherwise never match "CAP" in the glossary.
for _code in range(0xFF01, 0xFF5F):
    CHARACTER_EQUIVALENTS.setdefault(chr(_code), chr(_code - 0xFEE0))

# str.translate wants a dict keyed by code point, which str.maketrans builds.
_NORMALISE_TABLE = str.maketrans(CHARACTER_EQUIVALENTS)

# Which CSV columns hold the source term and the Japanese translation,
# for each language. Checked against the CSV header on load.
TERM_COLUMNS = {
    "en": ("term", "translation"),
    "ko": ("ハングル", "日本語"),
    "zh": ("中文", "日本語"),
}


class GlossaryManager:
    """Manages multiple glossary files and term lookups."""

    def __init__(self):
        self.glossaries = {
            code: self._empty_glossary() for code in TERM_COLUMNS
        }
        self.current_language = "en"

    @staticmethod
    def _empty_glossary():
        """The shape of one language's glossary entry."""
        return {
            "data": {},            # lowercased term -> {column name: value}
            "path": None,
            "header": [],
            "term_column": None,   # name of the column holding the source term
            "version": "1.0.0",
            "info": {"total_terms": 0, "unique_terms": 0, "last_updated": None},
            "pattern_ci": None,    # compiled regex, case-insensitive terms
            "pattern_cs": None,    # compiled regex, ALL-CAPS terms (exact case)
        }

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_glossary(self, file_path, language_code="en"):
        """
        Load glossary data from a CSV file for a specific language.

        Returns True on success, False otherwise.
        """
        if language_code not in self.glossaries:
            logger.error("Unknown language code: %s", language_code)
            return False

        glossary = self._empty_glossary()

        try:
            # utf-8-sig strips Excel's BOM if present, and is harmless if not.
            with open(file_path, "r", encoding="utf-8-sig", newline="") as csv_file:
                reader = csv.reader(csv_file)

                try:
                    header = [h.strip() for h in next(reader)]
                except StopIteration:
                    logger.error("CSV file is empty: %s", file_path)
                    return False

                indices = self._find_term_columns(language_code, header)
                if indices is None:
                    logger.error(
                        "Invalid glossary format in %s — header was %s",
                        file_path, header,
                    )
                    return False
                term_idx, translation_idx = indices

                ambiguous = set()
                for row in reader:
                    if len(row) <= max(term_idx, translation_idx):
                        continue

                    raw_term = row[term_idx].strip()
                    translation = row[translation_idx].strip()
                    if not raw_term or not translation:
                        continue

                    key = self.normalise(raw_term).lower()
                    if key in glossary["data"]:
                        # Same source term, different translation — e.g. CEH is
                        # both Center for Environmental Health and Centre for
                        # Ecology & Hydrology. Both are kept and both display.
                        ambiguous.add(raw_term)

                    # Keep every column, so the UI can show the full row.
                    column_data = {
                        name: (row[i].strip() if i < len(row) else "")
                        for i, name in enumerate(header)
                    }
                    glossary["data"].setdefault(key, []).append(column_data)

                if ambiguous:
                    logger.info(
                        "%s: %d term(s) with more than one entry: %s",
                        os.path.basename(file_path), len(ambiguous),
                        ", ".join(sorted(ambiguous)),
                    )

        except OSError as e:
            logger.error("Error reading glossary file %s: %s", file_path, e)
            return False

        glossary["header"] = header
        glossary["term_column"] = header[term_idx]
        glossary["path"] = file_path
        glossary["info"]["total_terms"] = sum(
            len(rows) for rows in glossary["data"].values()
        )
        glossary["info"]["unique_terms"] = len(glossary["data"])
        glossary["info"]["last_updated"] = datetime.now().isoformat()
        glossary["version"] = self.file_version(file_path)

        self.glossaries[language_code] = glossary
        self._build_patterns(language_code)

        logger.info(
            "Loaded %d terms from %s (v%s)",
            glossary["info"]["total_terms"], file_path, glossary["version"],
        )
        return True

    @staticmethod
    def _find_term_columns(language_code, header):
        """
        Locate the source-term and translation columns in the header.

        Returns (term_idx, translation_idx), or None if the header
        doesn't look like a glossary for this language.
        """
        term_name, translation_name = TERM_COLUMNS[language_code]

        if language_code == "en":
            # English headers are ASCII, so compare case-insensitively.
            lowered = [h.lower() for h in header]
            if term_name in lowered and translation_name in lowered:
                return lowered.index(term_name), lowered.index(translation_name)
            return None

        if term_name in header and translation_name in header:
            return header.index(term_name), header.index(translation_name)
        return None

    # ------------------------------------------------------------------
    # Pattern building
    # ------------------------------------------------------------------

    @staticmethod
    def _needs_exact_case(raw_term):
        """
        True if a term should only match when the text uses the same case.

        Applies to letters-only ALL-CAPS terms — acronyms like CAP, WHO, AND,
        whose lowercase forms are ordinary English words. Terms containing
        digits or punctuation (COVID-19, AFL-CIO) are excluded: their
        lowercase forms aren't real words, so matching them loosely is safe
        and catches variants like "Covid-19".
        """
        return raw_term.isupper() and raw_term.isalpha() and len(raw_term) > 1

    def _build_patterns(self, language_code):
        """
        Compile one regex per language holding every glossary term.

        Terms are sorted longest-first so that at any position in the text
        the longest term wins — "ready-to-eat" matches as one term rather
        than as "eat".
        """
        glossary = self.glossaries[language_code]
        term_column = glossary["term_column"]

        case_insensitive = []
        case_sensitive = []
        for key, rows in glossary["data"].items():
            raw_term = rows[0].get(term_column, key)
            if self._needs_exact_case(raw_term):
                case_sensitive.append(self.normalise(raw_term))
            else:
                case_insensitive.append(key)

        glossary["pattern_ci"] = self._compile_terms(
            case_insensitive, language_code, re.IGNORECASE
        )
        glossary["pattern_cs"] = self._compile_terms(
            case_sensitive, language_code, 0
        )

    @staticmethod
    def _compile_terms(terms, language_code, flags):
        """Build a single alternation regex from a list of terms."""
        if not terms:
            return None

        terms = sorted(set(terms), key=len, reverse=True)
        alternation = "|".join(re.escape(t) for t in terms)

        if language_code == "en":
            # Require a non-alphanumeric character (or string edge) on both
            # sides, so "cap" doesn't match inside "capture". Plain \b fails
            # on terms that start or end with punctuation, like "e-commerce".
            pattern = r"(?<![0-9A-Za-z])(?:" + alternation + r")(?![0-9A-Za-z])"
        else:
            # Korean and Chinese aren't space-delimited, so word boundaries
            # don't apply — match anywhere in the text.
            pattern = r"(?:" + alternation + r")"

        try:
            return re.compile(pattern, flags)
        except re.error as e:
            logger.error("Failed to compile glossary pattern: %s", e)
            return None

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    @staticmethod
    def normalise(text):
        """
        Replace typographic punctuation with ASCII equivalents.

        Excel and Word silently turn ' into ’ and - into –, so a term saved
        from a spreadsheet often won't match the same word typed or pasted
        from a web page. Normalising both sides removes the mismatch.

        The result is always the same length as the input, so match positions
        remain valid against the original text.
        """
        return text.translate(_NORMALISE_TABLE)

    def find_terms_in_text(self, text):
        """
        Find all glossary terms in the given text.

        Returns a list of row dicts, ordered by where each term first
        appears in the text. A term is reported once per occurrence in the
        glossary — an ambiguous term like CEH, which has two entries,
        contributes two consecutive rows.
        """
        glossary = self.glossaries[self.current_language]
        data = glossary["data"]
        if not text or not data:
            return []

        # Match against the normalised text so that curly and straight
        # punctuation are treated as the same character.
        text = self.normalise(text)

        hits = []  # (position, key)
        for pattern in (glossary["pattern_ci"], glossary["pattern_cs"]):
            if pattern is None:
                continue
            for match in pattern.finditer(text):
                key = match.group(0).lower()
                if key in data:
                    hits.append((match.start(), key))

        hits.sort(key=lambda hit: hit[0])

        results = []
        seen = set()
        for _, key in hits:
            if key not in seen:
                seen.add(key)
                # data[key] is a list: one entry normally, several if the
                # same source term has more than one translation.
                results.extend(data[key])
        return results

    def set_current_language(self, language_code):
        """Set the current language for term lookups."""
        if language_code in self.glossaries:
            self.current_language = language_code
            return True
        return False

    def get_term(self, term):
        """
        Look up a single term. Returns a list of matching rows, or None.
        """
        return self.glossaries[self.current_language]["data"].get(
            self.normalise(term.strip()).lower()
        )

    def get_all_terms(self):
        """Get all terms in the current language glossary."""
        return self.glossaries[self.current_language]["data"]

    def get_glossary_info(self):
        """Get information about the loaded glossary."""
        return self.glossaries[self.current_language]["info"]

    # ------------------------------------------------------------------
    # Paths and versions
    # ------------------------------------------------------------------

    @staticmethod
    def _read_json(path):
        """Read a JSON file, returning {} if it's missing or malformed."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Could not read %s: %s", path, e)
            return {}

    @staticmethod
    def version_tuple(version):
        """Turn '1.0.2' into (1, 0, 2) so versions can be compared."""
        try:
            return tuple(int(part) for part in str(version).split("."))
        except (ValueError, AttributeError):
            return (0, 0, 0)

    def file_version(self, file_path):
        """
        Read the real version of a glossary file from its manifest.

        Files in the user data dir are versioned by installed-versions.json,
        written by UpdateManager when it downloads them. Bundled files are
        versioned by the glossary-versions.json sitting beside them.

        Returns UNKNOWN_VERSION if no manifest records this file.
        """
        path = Path(file_path)
        filename = path.name
        user_glossaries_dir = self._get_user_data_dir() / "glossaries"

        if path.parent == user_glossaries_dir:
            manifest = self._read_json(
                self._get_user_data_dir() / INSTALLED_MANIFEST
            )
            # installed-versions.json maps filename -> version string.
            version = manifest.get(filename, UNKNOWN_VERSION)
        else:
            manifest = self._read_json(path.parent / BUNDLED_MANIFEST)
            # glossary-versions.json maps filename -> {"version": ..., ...}
            entry = manifest.get(filename) or {}
            version = entry.get("version", UNKNOWN_VERSION)

        logger.debug("Version of %s: %s", file_path, version)
        return version

    def choose_glossary_file(self, filename, candidate_dirs):
        """
        Pick which copy of a glossary file to load.

        Compares the recorded version of every copy that exists and returns
        the highest. Ties go to the copy listed first, so callers should put
        the user data dir first — a downloaded file that matches the bundled
        version is the one the updater intends to be authoritative.

        Returns (path, version), or (None, None) if no copy exists.
        """
        best_path = None
        best_version = None

        for directory in candidate_dirs:
            candidate = Path(directory) / filename
            if not candidate.is_file():
                continue

            version = self.file_version(candidate)
            if best_path is None or (
                self.version_tuple(version) > self.version_tuple(best_version)
            ):
                best_path, best_version = candidate, version

        if best_path is None:
            logger.warning("No copy of %s found in %s", filename, candidate_dirs)
            return None, None

        logger.info("Selected %s (v%s)", best_path, best_version)
        return str(best_path), best_version

    @staticmethod
    def _get_user_data_dir():
        """Get platform-specific user data directory."""
        if platform.system() == "Windows":
            app_data = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            return Path(app_data) / "SearchGlossary"
        return Path.home() / ".local" / "share" / "SearchGlossary"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 3:
        print("Usage: python glossary.py <path-to-csv> <en|ko|zh>")
        sys.exit(1)

    csv_path, lang = sys.argv[1], sys.argv[2]
    manager = GlossaryManager()
    if not manager.load_glossary(csv_path, lang):
        print("Failed to load glossary")
        sys.exit(1)

    manager.set_current_language(lang)
    print(f"Loaded {manager.get_glossary_info()['total_terms']} terms\n")

    sample = sys.stdin.read()
    if sample.strip():
        term_column = manager.glossaries[lang]["term_column"]
        for row in manager.find_terms_in_text(sample):
            print(f"{row[term_column]} -> {row[TERM_COLUMNS[lang][1]]}")