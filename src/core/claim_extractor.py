import re
from typing import Optional
from src.core.claim import ClaimDraft, ClaimLabel


class ClaimExtractor:
    LEAK_PHRASES = [
        "obviously",
        "clearly",
        "trivially",
        "well-known",
        "well known",
        "by symmetry",
        "by inspection",
        "it is easy to see",
        "it follows that",
        "without loss of generality",
        "WLOG",
        "straightforward",
        "immediate",
        "evident",
    ]
    
    DEFINITION_MARKERS = [
        "let",
        "define",
        "we define",
        "denote",
        "we denote",
        "set",
        "we set",
    ]
    
    EQUATION_PATTERNS = [
        r'\$\$[^$]+\$\$',
        r'\\begin\{equation\}.*?\\end\{equation\}',
        r'\\begin\{align\}.*?\\end\{align\}',
        r'\\begin\{eqnarray\}.*?\\end\{eqnarray\}',
        r'\\\[[^\]]+\\\]',
        r'\$[^$]+\$',
    ]

    def __init__(self):
        self.leak_pattern = re.compile(
            r'\b(' + '|'.join(re.escape(p) for p in self.LEAK_PHRASES) + r')\b',
            re.IGNORECASE
        )
        self.equation_patterns = [re.compile(p, re.DOTALL) for p in self.EQUATION_PATTERNS]

    def extract_claims(
        self,
        input_text: str,
        latex_blocks: Optional[list[str]] = None,
        code_blocks: Optional[list[str]] = None,
    ) -> list[ClaimDraft]:
        claims = []
        
        if latex_blocks:
            for block in latex_blocks:
                claims.extend(self._extract_from_latex(block))
        
        claims.extend(self._extract_from_text(input_text))
        
        return claims

    def _extract_from_latex(self, latex_block: str) -> list[ClaimDraft]:
        claims = []
        consumed_spans = []
        
        for pattern in self.equation_patterns:
            for match in pattern.finditer(latex_block):
                start, end = match.start(), match.end()
                
                overlaps = any(
                    (start < c_end and end > c_start)
                    for c_start, c_end in consumed_spans
                )
                if overlaps:
                    continue
                
                equation_text = match.group(0).strip()
                if self._is_substantive_equation(equation_text):
                    claims.append(
                        ClaimDraft(
                            statement=equation_text,
                            claim_span=(start, end),
                            suggested_label=ClaimLabel.DERIVED,
                        )
                    )
                    consumed_spans.append((start, end))
        
        return claims

    def _extract_from_text(self, text: str) -> list[ClaimDraft]:
        claims = []
        
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            sentence_claims = self._extract_from_sentence(sentence)
            claims.extend(sentence_claims)
        
        return claims

    def _split_sentences(self, text: str) -> list[str]:
        sentence_endings = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
        sentences = sentence_endings.split(text)
        return [s.strip() for s in sentences if s.strip()]

    def _extract_from_sentence(self, sentence: str) -> list[ClaimDraft]:
        claims = []
        
        if self._is_question(sentence):
            return claims
        
        if self._is_pure_definition(sentence):
            return claims
        
        if self._contains_leak_phrase(sentence):
            claims.append(
                ClaimDraft(
                    statement=sentence,
                    suggested_label=ClaimLabel.SPECULATIVE,
                )
            )
            return claims
        
        if self._contains_assertion(sentence):
            sub_claims = self._split_multi_claim_sentence(sentence)
            for claim_statement in sub_claims:
                label = self._infer_label(claim_statement)
                claims.append(
                    ClaimDraft(
                        statement=claim_statement,
                        suggested_label=label,
                    )
                )
        
        return claims

    def _is_question(self, sentence: str) -> bool:
        return sentence.strip().endswith('?')
    
    def _is_pure_definition(self, sentence: str) -> bool:
        lower = sentence.lower().strip()
        
        for marker in self.DEFINITION_MARKERS:
            if lower.startswith(marker + " "):
                if not self._contains_equality_or_relation(sentence):
                    return True
                
                if re.search(r'\b(be|equal|denote)\b', lower) and not re.search(r'\b(then|thus|therefore|hence|so)\b', lower):
                    return True
        
        return False

    def _contains_leak_phrase(self, sentence: str) -> bool:
        return bool(self.leak_pattern.search(sentence))

    def _contains_assertion(self, sentence: str) -> bool:
        assertion_patterns = [
            r'\b(is|are|equals?|becomes?)\b',
            r'\b(satisfies?|obeys?|follows?)\b',
            r'\b(implies?|yields?|gives?)\b',
            r'\b(therefore|thus|hence|so)\b',
            r'\bto be\b',
            r'[=<>≤≥≠≈∝]',
            r'\b(theorem|lemma|proposition|corollary)\b',
        ]
        
        for pattern in assertion_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                return True
        
        return False

    def _contains_equality_or_relation(self, sentence: str) -> bool:
        return bool(re.search(r'[=<>≤≥≠≈∝]', sentence))

    def _split_multi_claim_sentence(self, sentence: str) -> list[str]:
        if 'according to' in sentence.lower():
            return [sentence]
        
        conjunctions = [' and ', ' while ', ' whereas ', ', and ']
        
        parts = [sentence]
        for conj in conjunctions:
            new_parts = []
            for part in parts:
                if conj in part.lower():
                    split_parts = part.split(conj)
                    new_parts.extend(split_parts)
                else:
                    new_parts.append(part)
            parts = new_parts
        
        substantive_parts = []
        for part in parts:
            part = part.strip().rstrip(',;')
            if self._is_substantive_claim(part):
                substantive_parts.append(part)
        
        if len(substantive_parts) == 0:
            return [sentence]
        
        return substantive_parts

    def _is_substantive_claim(self, text: str) -> bool:
        if len(text.split()) < 3:
            return False
        
        if self._contains_assertion(text):
            return True
        
        return False

    def _is_substantive_equation(self, equation_text: str) -> bool:
        if len(equation_text.strip()) < 3:
            return False
        
        if '=' not in equation_text:
            return False
        
        return True

    def _infer_label(self, claim_text: str) -> ClaimLabel:
        lower = claim_text.lower()
        
        if any(word in lower for word in ['therefore', 'thus', 'hence', 'implies', 'follows', 'derive']):
            return ClaimLabel.DERIVED
        
        if any(word in lower for word in ['compute', 'calculate', 'evaluate', 'numerical', 'simulate']):
            return ClaimLabel.COMPUTED
        
        if any(word in lower for word in ['theorem', 'lemma', 'proposition', 'according to', 'from ref', 'cite', 'citation']):
            return ClaimLabel.CITED
        
        return ClaimLabel.SPECULATIVE


def extract_claims(
    input_text: str,
    latex_blocks: Optional[list[str]] = None,
    code_blocks: Optional[list[str]] = None,
) -> list[ClaimDraft]:
    extractor = ClaimExtractor()
    return extractor.extract_claims(input_text, latex_blocks, code_blocks)
