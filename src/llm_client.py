import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
)
MODEL = os.environ["LLM_MODEL"]

def complete(prompt, system=None, temperature=0.0):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.appned({"role": "user", "content": prompt})
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature
    )

    return resp.choices[0].message.content

if __name__ == "__main__":
    print(complete("Reply with the single word: ok"))