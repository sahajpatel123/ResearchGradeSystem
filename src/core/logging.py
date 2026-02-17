import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.core.claim import Claim, ClaimDraft


class ClaimLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "claim_extraction.jsonl"

    def compute_input_hash(self, input_text: str) -> str:
        return hashlib.sha256(input_text.encode('utf-8')).hexdigest()

    def log_extraction(
        self,
        input_text: str,
        claims: list[ClaimDraft],
        run_id: Optional[str] = None,
    ) -> str:
        input_hash = self.compute_input_hash(input_text)
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "input_hash": input_hash,
            "input_length": len(input_text),
            "extracted_claims": [
                {
                    "statement": c.statement,
                    "suggested_label": c.suggested_label.value,
                    "claim_span": c.claim_span,
                }
                for c in claims
            ],
            "claim_count": len(claims),
        }
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
        
        return input_hash

    def log_finalization_check(
        self,
        claims: list[Claim],
        can_finalize: bool,
        reasons: list[str],
        run_id: Optional[str] = None,
    ) -> None:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "event": "finalization_check",
            "can_finalize": can_finalize,
            "reasons": reasons,
            "total_claims": len(claims),
            "non_speculative_claims": len([c for c in claims if c.claim_label.value != "SPECULATIVE"]),
        }
        
        finalization_log = self.log_dir / "finalization.jsonl"
        with open(finalization_log, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
