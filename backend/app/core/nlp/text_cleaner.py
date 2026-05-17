"""
Text Cleaner for NLP Processing
Preprocesses raw OCR text for better NLP performance
"""

import re
import unicodedata
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class TextCleaner:
    """
    Text preprocessing and cleaning for NLP tasks
    Removes noise, normalizes text, and prepares for classification/NER
    """
    
    def __init__(self):
        """Initialize text cleaner with default patterns"""
        self.setup_patterns()
    
    def setup_patterns(self):
        """Setup regex patterns for text cleaning"""
        self.patterns = {
            # Remove extra whitespace
            'multiple_spaces': re.compile(r'\s+'),
            
            # Remove page numbers and headers
            'page_numbers': re.compile(r'\n\s*page\s+\d+\s*\n', re.IGNORECASE),
            
            # Remove OCR artifacts
            'ocr_artifacts': re.compile(r'[^\w\s.,!?;:()\-$€£₹%#@&*+=<>/\\|"\'`~\[\]{}]'),
            
            # Remove email signatures
            'email_signature': re.compile(r'--\s*\n.*?(?=\n\n|\Z)', re.DOTALL),
            
            # Remove URLs
            'urls': re.compile(r'https?://\S+|www\.\S+'),
            
            # Normalize dashes
            'dashes': re.compile(r'[—–]'),
            
            # Normalize quotes
            'quotes': re.compile(r'[""]'),
            
            # Remove line numbers
            'line_numbers': re.compile(r'^\s*\d+\s+', re.MULTILINE),
            
            # Remove table artifacts
            'table_artifacts': re.compile(r'[|+\-=]{3,}'),
            
            # Remove repeated characters
            'repeated_chars': re.compile(r'(.)\1{4,}')
        }
    
    def clean_text(
        self,
        text: str,
        remove_stopwords: bool = False,
        normalize_unicode: bool = True,
        lowercase: bool = True,
        remove_numbers: bool = False,
        min_word_length: int = 2
    ) -> str:
        """
        Clean and preprocess text for NLP
        
        Args:
            text: Raw input text
            remove_stopwords: Remove common stopwords
            normalize_unicode: Normalize Unicode characters
            lowercase: Convert to lowercase
            remove_numbers: Remove numeric characters
            min_word_length: Minimum word length to keep
        
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Normalize unicode
        if normalize_unicode:
            text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        
        # Apply regex patterns
        for pattern_name, pattern in self.patterns.items():
            if pattern_name != 'ocr_artifacts' or not remove_numbers:
                text = pattern.sub(' ', text)
        
        # Remove OCR artifacts (optional character removal)
        if not remove_numbers:
            # Keep numbers when not removing
            ocr_pattern = re.compile(r'[^\w\s.,!?;:()\-$€£₹%#@&*+=<>/\\|"\'`~\[\]{}0-9]')
            text = ocr_pattern.sub(' ', text)
        else:
            text = self.patterns['ocr_artifacts'].sub(' ', text)
        
        # Remove numbers if requested
        if remove_numbers:
            text = re.sub(r'\b\d+\b', '', text)
        
        # Convert to lowercase
        if lowercase:
            text = text.lower()
        
        # Remove stopwords
        if remove_stopwords:
            text = self._remove_stopwords(text)
        
        # Normalize whitespace
        text = self.patterns['multiple_spaces'].sub(' ', text)
        
        # Remove short words
        if min_word_length > 1:
            words = text.split()
            words = [w for w in words if len(w) >= min_word_length]
            text = ' '.join(words)
        
        return text.strip()
    
    def _remove_stopwords(self, text: str) -> str:
        """Remove common stopwords from text"""
        stopwords = {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'were', 'will', 'with', 'i', 'you', 'we', 'they',
            'this', 'that', 'these', 'those', 'such', 'which', 'who', 'whom'
        }
        
        words = text.split()
        words = [w for w in words if w not in stopwords]
        return ' '.join(words)
    
    def extract_sentences(self, text: str, max_sentences: int = None) -> List[str]:
        """
        Split text into sentences
        
        Args:
            text: Input text
            max_sentences: Maximum number of sentences to return
        
        Returns:
            List of sentences
        """
        # Simple sentence splitting
        sentence_delimiters = re.compile(r'[.!?]+')
        sentences = sentence_delimiters.split(text)
        
        # Clean each sentence
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
        
        if max_sentences:
            sentences = sentences[:max_sentences]
        
        return sentences
    
    def extract_paragraphs(self, text: str, min_paragraph_length: int = 50) -> List[str]:
        """
        Extract paragraphs from text
        
        Args:
            text: Input text
            min_paragraph_length: Minimum characters for a paragraph
        
        Returns:
            List of paragraphs
        """
        # Split by double newlines
        paragraphs = re.split(r'\n\s*\n', text)
        
        # Clean and filter
        paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > min_paragraph_length]
        
        return paragraphs
    
    def normalize_whitespace(self, text: str) -> str:
        """Normalize all whitespace to single spaces"""
        return self.patterns['multiple_spaces'].sub(' ', text).strip()
    
    def remove_special_characters(self, text: str, keep_chars: str = '') -> str:
        """
        Remove special characters from text
        
        Args:
            text: Input text
            keep_chars: Characters to keep (e.g., '.,!?')
        
        Returns:
            Cleaned text
        """
        if keep_chars:
            pattern = f'[^\w\s{re.escape(keep_chars)}]'
        else:
            pattern = r'[^\w\s]'
        
        return re.sub(pattern, ' ', text)
    
    def correct_ocr_errors(self, text: str) -> str:
        """
        Correct common OCR errors
        
        Args:
            text: Text with potential OCR errors
        
        Returns:
            Corrected text
        """
        corrections = {
            # Common OCR substitutions
            '0': 'O',
            '1': 'I',
            '5': 'S',
            '8': 'B',
            'rn': 'm',
            'cl': 'd',
            'vv': 'w',
            # Number corrections
            'rn': 'm',
            'vv': 'w',
            'il': 'li',
        }
        
        for wrong, correct in corrections.items():
            text = text.replace(wrong, correct)
        
        return text
    
    def extract_key_phrases(self, text: str, max_phrases: int = 10) -> List[str]:
        """
        Extract key phrases from text using statistical methods
        
        Args:
            text: Input text
            max_phrases: Maximum number of phrases to extract
        
        Returns:
            List of key phrases
        """
        # Simple tf-idf based extraction (simplified)
        words = self.clean_text(text, remove_stopwords=True).split()
        
        # Count word frequencies
        freq = {}
        for word in words:
            freq[word] = freq.get(word, 0) + 1
        
        # Get common n-grams
        ngrams = []
        for i in range(len(words) - 2):
            phrase = ' '.join(words[i:i+3])
            ngrams.append(phrase)
        
        # Count phrase frequencies
        phrase_freq = {}
        for phrase in ngrams:
            phrase_freq[phrase] = phrase_freq.get(phrase, 0) + 1
        
        # Sort by frequency
        sorted_phrases = sorted(phrase_freq.items(), key=lambda x: x[1], reverse=True)
        
        return [phrase for phrase, count in sorted_phrases[:max_phrases]]
    
    def get_text_stats(self, text: str) -> Dict[str, Any]:
        """
        Get statistics about the text
        
        Args:
            text: Input text
        
        Returns:
            Dictionary with text statistics
        """
        cleaned = self.clean_text(text, lowercase=False, remove_stopwords=False)
        words = cleaned.split()
        
        stats = {
            "characters": len(text),
            "characters_no_spaces": len(text.replace(' ', '')),
            "words": len(words),
            "sentences": len(self.extract_sentences(text)),
            "paragraphs": len(self.extract_paragraphs(text)),
            "avg_word_length": sum(len(w) for w in words) / len(words) if words else 0,
            "unique_words": len(set(w.lower() for w in words)),
            "estimated_reading_time_minutes": len(words) / 200,  # 200 words per minute
        }
        
        return stats