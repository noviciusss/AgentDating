"""
Generic Apify actor runner with retry and timeout.
"""

import asyncio
import logging
from typing import Any, Optional

from apify_client import ApifyClient

from app.config import APIFY_TOKEN, SCRAPE_TIMEOUT

logger = logging.getLogger(__name__)


def _get_client() -> ApifyClient:
    """Get an Apify client instance."""
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN is not set")
    return ApifyClient(APIFY_TOKEN)


async def run_actor(
    actor_id: str,
    run_input: dict[str, Any],
    timeout: int = SCRAPE_TIMEOUT,
    max_retries: int = 1,
) -> Optional[list[dict]]:
    """Run an Apify actor and return results.

    Retries once on failure. Returns None if all attempts fail.
    Runs the synchronous Apify client in a thread executor.
    """
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Running actor {actor_id} (attempt {attempt + 1})")
            loop = asyncio.get_event_loop()

            def _run():
                client = _get_client()
                run = client.actor(actor_id).call(
                    run_input=run_input,
                    timeout_secs=timeout,
                )
                # Get dataset items
                dataset_id = run.get("defaultDatasetId")
                if not dataset_id:
                    return []
                items = list(client.dataset(dataset_id).iterate_items())
                return items

            result = await loop.run_in_executor(None, _run)
            logger.info(f"Actor {actor_id} returned {len(result)} items")
            return result

        except Exception as e:
            logger.warning(f"Actor {actor_id} failed (attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(2)
            else:
                return None

    return None
