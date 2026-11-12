---
id: py-refactor-sync-to-async
title: Python sync to async conversion (single file)
keywords: async, await, asincrono, sincrono, asyncio, gather, coroutine, awaitable
---
# Recipe: sync to async conversion (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import asyncio


async def {{ ASYNC FUNCTION }}({{ PARAMS }}):
    """{{ WHAT IT COMPUTES }} (asincrona)."""
    await asyncio.sleep(0)  # punto di sospensione
    return {{ RESULT }}


async def main():
    result = await {{ ASYNC FUNCTION }}({{ ARGUMENTS }})
    print(f"{{ MARKER }}={result}")


if __name__ == "__main__":
    asyncio.run(main())
```

RULES:
- ONE file only: project/main.py. Standard library only.
- Convert `def` to `async def` for the target function.
- Add `await` before any async call (including asyncio.sleep).
- Use `asyncio.run(main())` as entry point, NOT `main()`.
- Do NOT change the logic or output of the program.
- If multiple async calls, use `asyncio.gather()` for concurrency.