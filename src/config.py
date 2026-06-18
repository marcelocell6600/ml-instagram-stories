from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    ml_site_id: str
    ml_query: str
    ml_limit: int
    ml_min_price: float | None
    ml_max_price: float | None
    ml_access_token: str
    ml_affiliate_tag: str
    ig_user_id: str
    ig_access_token: str
    public_base_url: str
    upload_endpoint: str
    upload_secret: str
    output_dir: str


def _optional_float(value: str) -> float | None:
    if not value:
        return None
    return float(value)


def load_config() -> Config:
    load_dotenv()

    return Config(
        ml_site_id=os.getenv("ML_SITE_ID", "MLB"),
        ml_query=os.getenv("ML_QUERY", "ofertas tecnologia"),
        ml_limit=int(os.getenv("ML_LIMIT", "10")),
        ml_min_price=_optional_float(os.getenv("ML_MIN_PRICE", "")),
        ml_max_price=_optional_float(os.getenv("ML_MAX_PRICE", "")),
        ml_access_token=os.getenv("ML_ACCESS_TOKEN", ""),
        ml_affiliate_tag=os.getenv("ML_AFFILIATE_TAG", ""),
        ig_user_id=os.getenv("IG_USER_ID", ""),
        ig_access_token=os.getenv("IG_ACCESS_TOKEN", ""),
        public_base_url=os.getenv("PUBLIC_BASE_URL", "").rstrip("/"),
        upload_endpoint=os.getenv("UPLOAD_ENDPOINT", ""),
        upload_secret=os.getenv("UPLOAD_SECRET", ""),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
    )
