"""Bronze schema transformation for Databricks ingestion."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class TitleNode:
    """Transforms GraphQL title nodes into structured records for Databricks."""
    
    ENDPOINT = "https://caching.graphql.imdb.com/"
    
    @staticmethod
    def transform(node: Dict[str, Any], page_no: int) -> Dict[str, Any]:
        """Transform a GraphQL title node into a Bronze record.
        
        Ensures consistent schema and types across records for Databricks bronze ingestion.
        
        Args:
            node: GraphQL title node
            page_no: Page number (0-indexed)
            
        Returns:
            Bronze record dict with 40+ fields
        """
        title_obj: Dict[str, Any] = node.get("title") or node

        title_type = title_obj.get("titleType") or {}
        primary_image = title_obj.get("primaryImage") or {}
        release_year = title_obj.get("releaseYear") or {}
        ratings_summary = title_obj.get("ratingsSummary") or {}
        runtime = title_obj.get("runtime") or {}
        certificate = title_obj.get("certificate") or {}
        can_rate = title_obj.get("canRate") or {}
        title_genres = title_obj.get("titleGenres") or {}
        latest_trailer = title_obj.get("latestTrailer") or {}
        plot_text_obj = (title_obj.get("plot") or {}).get("plotText") or {}
        release_date = title_obj.get("releaseDate") or {}
        production_status = title_obj.get("productionStatus") or {}
        metacritic = title_obj.get("metacritic") or {}

        genres_raw = title_genres.get("genres") or []
        genres_list = [g.get("genre", {}).get("text") for g in genres_raw if isinstance(g, dict)]

        record: Dict[str, Any] = {
            "title_id": str(title_obj.get("id") or ""),
            "title_text": str((title_obj.get("titleText") or {}).get("text") or ""),
            "original_title_text": str((title_obj.get("originalTitleText") or {}).get("text") or ""),
            "primary_image_url": str(primary_image.get("url") or ""),
            "certificate_rating": str(certificate.get("rating") or ""),
            "latest_trailer_id": str(latest_trailer.get("id") or ""),
            "plot_text": str(plot_text_obj.get("plainText") or ""),

            "release_year": int(release_year.get("year")) if isinstance(release_year.get("year"), int) else None,
            "aggregate_rating": float(ratings_summary.get("aggregateRating")) if isinstance(ratings_summary.get("aggregateRating"), (int, float)) else None,
            "vote_count": int(ratings_summary.get("voteCount")) if isinstance(ratings_summary.get("voteCount"), int) else None,
            "runtime_seconds": int(runtime.get("seconds")) if isinstance(runtime.get("seconds"), int) else None,
            "metacritic_metascore": int((metacritic.get("metascore") or {}).get("score")) if isinstance((metacritic.get("metascore") or {}).get("score"), int) else None,

            "can_rate": bool(can_rate.get("isRatable")) if isinstance(can_rate.get("isRatable"), bool) else False,

            "genres_list": genres_list,
            "release_year_list": [release_year.get("year"), release_year.get("endYear")] if release_year else [],

            "title_type_dict": title_type if isinstance(title_type, dict) else {},
            "primary_image_dict": primary_image if isinstance(primary_image, dict) else {},
            "ratings_summary_dict": ratings_summary if isinstance(ratings_summary, dict) else {},
            "release_year_dict": release_year if isinstance(release_year, dict) else {},
            "title_genres_dict_list": genres_raw if isinstance(genres_raw, list) else [],
            "release_date_dict": release_date if isinstance(release_date, dict) else {},
            "production_status_dict": production_status if isinstance(production_status, dict) else {},
            "metacritic_dict": metacritic if isinstance(metacritic, dict) else {},
            "series_dict": title_obj.get("series") if isinstance(title_obj.get("series"), dict) else {},

            "title_type_text": str(title_type.get("text") or ""),
            "production_status_stage": str((production_status.get("currentProductionStage") or {}).get("id") or (production_status.get("currentProductionStage") or {}).get("text") or ""),

            "page": page_no + 1,
            "source_url": TitleNode.ENDPOINT,
            "scraped_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        return record
