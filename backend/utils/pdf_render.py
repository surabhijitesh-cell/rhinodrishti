"""Run PDF drawing away from the server's main loop, one PDF at a time."""
import asyncio

# One at a time: each PDF can draw several large maps on a 512 MB server.
_render_slot = asyncio.Semaphore(1)


async def render_pdf_off_loop(render, *args, **kwargs):
    async with _render_slot:
        return await asyncio.to_thread(render, *args, **kwargs)
