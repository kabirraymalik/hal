class Skill:
    def __init__(self):
        self.name = "skill"
        self.description = "description"
        self.input = "type: input description"
        self.output = "string: output description"
        self.context_builder = False  # DeBERTa only trains for context_builder skills
        self.time_out = 100  # ms
        self.tags = ["list", "of", "keywords", "that", "could", "trigger", "this", "skill"]  # for dataset gen

    async def use(self, input_str = ""):
        return ""