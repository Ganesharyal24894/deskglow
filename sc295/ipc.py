"""Newline-delimited JSON over a unix domain socket (daemon <-> CLI)."""
import asyncio
import json


async def read_message(reader):
    line = await reader.readline()
    if not line:
        return None
    return json.loads(line.decode())


async def write_message(writer, obj):
    writer.write((json.dumps(obj) + "\n").encode())
    await writer.drain()


async def request(socket_path, obj, timeout=25.0):
    """Connect, send one request, return the one-line JSON reply."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_unix_connection(socket_path), timeout=5.0)
    try:
        await write_message(writer, obj)
        return await asyncio.wait_for(read_message(reader), timeout=timeout)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
