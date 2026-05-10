import asyncio

from dotenv import load_dotenv

load_dotenv()

import llm


async def main():
    message = "Say hello in one short sentence."
    model = llm.pick_model(message)
    print(f"picked model: {model}")

    result = await llm.chat(
        messages=[{"role": "user", "content": message}],
        system="You are Zee, a concise assistant.",
        model=model,
    )

    print("stop_reason:", result["stop_reason"])
    print("usage:", result["usage"])
    print("content:", result["content"])


if __name__ == "__main__":
    asyncio.run(main())
