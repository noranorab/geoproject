from pystac import Item
from pystac_client import Client

from wildfirewatch.config import get_settings


def search_scenes(
    bbox: tuple[float, float, float, float],
    start_date: str,
    end_date: str,
    max_cloud_cover: float = 20.0,
    limit: int = 10,
) -> list[Item]:
    """Query Earth Search STAC for Sentinel-2 L2A scenes intersecting bbox/date range."""
    settings = get_settings()
    catalog = Client.open(settings.stac_api_url)
    # `limit` is the STAC API's per-page size, not a result cap — pystac_client paginates
    # through everything unless `max_items` bounds the total, so both are needed here.
    search = catalog.search(
        collections=[settings.stac_collection],
        bbox=bbox,
        datetime=f"{start_date}/{end_date}",
        limit=min(limit, 100),
        max_items=limit,
    )
    items = list(search.items())
    items = [i for i in items if i.properties.get("eo:cloud_cover", 100) <= max_cloud_cover]
    items.sort(key=lambda i: i.properties.get("eo:cloud_cover", 100))
    return items
