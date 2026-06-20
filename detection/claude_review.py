import os

import anthropic
from dotenv import load_dotenv


load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

CLAUDE_SYSTEM_PROMPT = """You are a safety expert analyzing a sequence of CCTV observations for elderly care monitoring.
Analyze the FULL CONTEXT of the provided log and classify the final situation as one of:
1. FALL - The person ultimately fell, collapsed, slipped, or lost consciousness.
2. CAUTION - Unstable, wobbling, or almost fell, but recovered or hasn't fallen.
3. NORMAL - Voluntary actions, resting, sleeping, or normal activities.

Respond ONLY in this format:
VERDICT: FALL or CAUTION or NORMAL
REASON: (one line explanation based on the full context)
"""

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def claude_analyze(full_text: str) -> dict:
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=200,
            system=CLAUDE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"[CCTV Full Sequence Log]\n{full_text}"}],
        )
        result = response.content[0].text.strip()
        verdict, reason = "UNKNOWN", result

        for line in result.split("\n"):
            line_upper = line.upper()
            if "VERDICT" in line_upper:
                if "FALL" in line_upper and "CAUTION" not in line_upper:
                    verdict = "FALL"
                elif "CAUTION" in line_upper:
                    verdict = "CAUTION"
                elif "NORMAL" in line_upper:
                    verdict = "NORMAL"
            if "REASON" in line_upper:
                reason = line.split(":", 1)[-1].strip()

        return {"verdict": verdict, "reason": reason}
    except Exception as exc:
        return {"verdict": "ERROR", "reason": f"Claude error: {exc}"}
