import json
import tempfile
from pathlib import Path
from src.core.logging import ClaimLogger
from src.core.claim import ClaimDraft, Claim, ClaimLabel


class TestClaimLogger:
    
    def test_compute_input_hash_deterministic(self):
        logger = ClaimLogger(log_dir=tempfile.mkdtemp())
        text = "The energy is E = mc^2."
        
        hash1 = logger.compute_input_hash(text)
        hash2 = logger.compute_input_hash(text)
        
        assert hash1 == hash2
        assert len(hash1) == 64
    
    def test_compute_input_hash_different_inputs(self):
        logger = ClaimLogger(log_dir=tempfile.mkdtemp())
        text1 = "The energy is E = mc^2."
        text2 = "The force is F = ma."
        
        hash1 = logger.compute_input_hash(text1)
        hash2 = logger.compute_input_hash(text2)
        
        assert hash1 != hash2
    
    def test_log_extraction_creates_file(self):
        log_dir = tempfile.mkdtemp()
        logger = ClaimLogger(log_dir=log_dir)
        
        text = "The energy is E = mc^2."
        claims = [ClaimDraft(statement="E = mc^2", suggested_label=ClaimLabel.DERIVED)]
        
        input_hash = logger.log_extraction(text, claims, run_id="test_run_1")
        
        assert Path(log_dir, "claim_extraction.jsonl").exists()
        assert input_hash == logger.compute_input_hash(text)
    
    def test_log_extraction_content(self):
        log_dir = tempfile.mkdtemp()
        logger = ClaimLogger(log_dir=log_dir)
        
        text = "The energy is E = mc^2."
        claims = [
            ClaimDraft(statement="E = mc^2", suggested_label=ClaimLabel.DERIVED, claim_span=(14, 23))
        ]
        
        logger.log_extraction(text, claims, run_id="test_run_2")
        
        with open(Path(log_dir, "claim_extraction.jsonl"), 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            assert entry["run_id"] == "test_run_2"
            assert entry["claim_count"] == 1
            assert entry["extracted_claims"][0]["statement"] == "E = mc^2"
            assert entry["extracted_claims"][0]["suggested_label"] == "DERIVED"
            assert entry["extracted_claims"][0]["claim_span"] == [14, 23]
    
    def test_log_finalization_check(self):
        log_dir = tempfile.mkdtemp()
        logger = ClaimLogger(log_dir=log_dir)
        
        claims = [
            Claim.create("claim 1", ClaimLabel.DERIVED),
            Claim.create("claim 2", ClaimLabel.SPECULATIVE),
        ]
        
        logger.log_finalization_check(
            claims,
            can_finalize=False,
            reasons=["Missing evidence for claim 1"],
            run_id="test_run_3"
        )
        
        finalization_log = Path(log_dir, "finalization.jsonl")
        assert finalization_log.exists()
        
        with open(finalization_log, 'r') as f:
            lines = f.readlines()
            assert len(lines) == 1
            
            entry = json.loads(lines[0])
            assert entry["run_id"] == "test_run_3"
            assert entry["can_finalize"] is False
            assert entry["reasons"] == ["Missing evidence for claim 1"]
            assert entry["total_claims"] == 2
            assert entry["non_speculative_claims"] == 1
    
    def test_log_multiple_extractions(self):
        log_dir = tempfile.mkdtemp()
        logger = ClaimLogger(log_dir=log_dir)
        
        text1 = "First text."
        text2 = "Second text."
        claims1 = [ClaimDraft(statement="claim 1", suggested_label=ClaimLabel.DERIVED)]
        claims2 = [ClaimDraft(statement="claim 2", suggested_label=ClaimLabel.COMPUTED)]
        
        logger.log_extraction(text1, claims1, run_id="run_1")
        logger.log_extraction(text2, claims2, run_id="run_2")
        
        with open(Path(log_dir, "claim_extraction.jsonl"), 'r') as f:
            lines = f.readlines()
            assert len(lines) == 2
