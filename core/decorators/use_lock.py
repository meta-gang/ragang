from asyncio import Lock


def use_async_lock(lock: Lock):
    def decorator(method):
        async def wrapper(*args, **kwargs):
            async with lock:  # event-driven wait until lock acquired
                return await method(*args, **kwargs)
        return wrapper
    return decorator

# any other lock decorations...