class Relevance:
    def __init__(self, skill_name, value):
        self.skill_name = skill_name
        self.value = value

class DeBERTaSmall:
    def __init__(self):
        # load DeBERTa-v3-small weights
        self.model = None
        self.tokenizer = None
        self.thinking = False

    def is_thinking(self):
        return self.thinking

    def predict(self, prompt):
        """Returns float 0-1: probability that skills are needed."""
        self.thinking = True
        # TODO: tokenize, forward pass, sigmoid
        self.thinking = False
        return 0.8

class DeBERTaBase:
    def __init__(self, skill_names):
        # load DeBERTa-v3-base weights
        # skill_names defines the output head order
        self.model = None
        self.tokenizer = None
        self.skill_names = skill_names
        self.thinking = False

    def is_thinking(self):
        return self.thinking

    def predict(self, prompt):
        """Returns list of Relevances, one per skill."""
        self.thinking = True
        # TODO: tokenize, forward pass, sigmoid per skill
        self.thinking = False
        return [Relevance(name, 0.5) for name in self.skill_names]