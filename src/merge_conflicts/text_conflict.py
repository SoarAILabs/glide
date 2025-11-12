<<<<<<< HEAD

import re


def normalize_whitespace(text):
    """Normalize all whitespace to single spaces and trim ends"""
    return " ".join(text.split())


def split_sentences(text):
    """Split text on sentence boundaries .!? with following spaces"""
    return re.split(r'(?<=[.!?])\s+', text.strip())


def word_frequencies(text):
    """Count lowercase token frequencies ignoring punctuation"""
    tokens = re.findall(r"\b\w+\b", normalize_whitespace(text).lower())
    freq = {}
    for t in tokens:
        freq[t] = freq.get(t, 0) + 1
    return freq
||||||| base
import re


def normalize_whitespace(text):
    """Normalize whitespace by stripping ends"""
    return text.strip()
s

def split_sentences(text):
    """Split sentences on periods only"""
    return [s for s in text.strip().split(".") if s]


def word_frequencies(text):
    """Count token frequencies case-sensitive"""
    tokens = re.findall(r"\b\w+\b", text)
    counts = {}
    for t in tokens:
        counts[t] = counts.get(t, 0) + 1
    return counts
=======
import re


def normalize_whitespace(text):
    """Replace all runs of whitespace with a single space"""
    return re.sub(r"\s+", " ", text).strip()


def split_sentences(text):
    """Split sentences handling spaces and keep delimiters removed"""
    parts = re.split(r"([.!?])", text.strip())
    sentences = []
    for i in range(0, len(parts) - 1, 2):
        sentences.append((parts[i] + parts[i + 1]).strip())
    if len(parts) % 2 == 1 and parts[-1]:
        sentences.append(parts[-1].strip())
    return sentences


def word_frequencies(text):
    """Count token frequencies ignoring stop punctuation and hyphens"""
    tokens = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", normalize_whitespace(text).lower())
    from collections import Counter

    return dict(Counter(tokens))
>>>>>>> branch
