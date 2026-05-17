import sys

class InteractionManager:
    _headless = False
    _auto_yes = False

    @classmethod
    def configure(cls, headless: bool = False, auto_yes: bool = False):
        cls._headless = headless
        cls._auto_yes = auto_yes

    @classmethod
    def ask(cls, prompt: str, default: bool = False) -> bool:
        if cls._headless:
            ans = cls._auto_yes or default
            print(f"{prompt} (Headless mode: auto-defaulting to {'y' if ans else 'N'})")
            return ans
            
        ans = input(prompt).strip().lower()
        if not ans:
            return default
        return ans == 'y'

def ask_user(prompt: str, default: bool = False) -> bool:
    return InteractionManager.ask(prompt, default)
