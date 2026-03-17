class SkillData:
    def __init__(self):
        self.tags = []
        self.complementary_skills = []
        self.confusion_skills = []
        self.usage_hints = []
        self.example_prompts = []
        self.wrong_skill_prompts = []
        self.no_skill_prompts = []

class Skill:
    def __init__(self):
        self.name = "skill"
        self.description = "description"
        self.input = "type: input description"
        self.output = "string: output description"
        self.time_out = 100  # ms
        self.datagen = None # or SkillData(), DeBERTa only trains for context_builder skills
        # ======================== for synthetic dataset generation =========================
        if self.datagen is not None:
            self.datagen.tags = ["list", "of", "keywords", "that", "could", "trigger", "this", "skill"]
            self.datagen.complementary_skills = ["skills", "often", "used", "alongside"]
            self.datagen.confusion_skills = ["skills", "often", "confused", "for"]
            self.datagen.usage_hints = [
                "tips on what makes using this skill tricky",
                "extra information that may be helpful for useful dataset seeding"
            ]
            self.datagen.example_prompts = [
                "at least 3 example inputs that should trigger this skill",
                "variety is good, implicit usage and not just direct requests"
            ]
            self.datagen.wrong_skill_prompts = [
                "at least 3 example inputs that should NOT trigger this skill, but trigger a different one",
                "bonus points if they seem to trigger this skill, but shouldn't and exclusively trigger others"
            ]
            self.datagen.no_skill_prompts = [
                "at least 3 example inputs that should NOT trigger ANY skill at all",
                "bonus points if they seem to trigger this skill, but should actually trigger no skill"
            ]

    async def use(self, input_str = ""):
        return ""