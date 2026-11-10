"""The semantic layer: metric and dimension definitions, loaded from metrics.yaml."""
import os
import yaml

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Layer:
    def __init__(self, path=None):
        raw = yaml.safe_load(open(path or os.path.join(HERE, "metrics.yaml"), encoding="utf-8"))
        self.metrics = raw["metrics"]
        self.dimensions = raw["dimensions"]
        self.ambiguous = raw.get("ambiguous", {})
        self.synonym = {}
        for name, m in self.metrics.items():
            for s in m["synonyms"] + [name.replace("_", " ")]:
                self.synonym[s.lower()] = name

    def find_metric(self, text):
        """Longest synonym first, so 'average order value' beats 'order'."""
        text = text.lower()
        for s in sorted(self.synonym, key=len, reverse=True):
            if s in text:
                return self.synonym[s]
        return None

    def find_ambiguous(self, text):
        for word, options in self.ambiguous.items():
            if f" {word} " in f" {text.lower()} " and not self.find_metric(text):
                return word, options
        return None
