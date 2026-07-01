"""Canonical data model for the Multi-Source Candidate Data Transformer."""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class ProvenancedValue:
    """A single value plus where it came from and how it was derived."""
    value: object
    source: str        # e.g. "csv", "ats_json", "resume", "notes"
    method: str         # e.g. "direct", "regex", "merge:csv+resume"
    confidence: float   # 0..1


@dataclass
class RawRecord:
    """One record extracted from one source, before merging. Loosely typed
    on purpose -- the extractor's job is just to pull out candidate
    fields with confidence, the merger reconciles them."""
    source: str
    candidate_key: str  # best-effort match key (lowercased email or name)
    full_name: Optional[ProvenancedValue] = None
    emails: list = field(default_factory=list)        # list[ProvenancedValue[str]]
    phones: list = field(default_factory=list)         # list[ProvenancedValue[str]]
    location: Optional[ProvenancedValue] = None        # ProvenancedValue[dict]
    links: dict = field(default_factory=dict)           # name -> ProvenancedValue[str]
    headline: Optional[ProvenancedValue] = None
    years_experience: Optional[ProvenancedValue] = None
    skills: list = field(default_factory=list)          # list[ProvenancedValue[str]]
    experience: list = field(default_factory=list)      # list[ProvenancedValue[dict]]
    education: list = field(default_factory=list)       # list[ProvenancedValue[dict]]
    errors: list = field(default_factory=list)          # extraction-time problems (non-fatal)
