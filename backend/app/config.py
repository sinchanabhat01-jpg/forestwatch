import os
from dotenv import load_dotenv

load_dotenv()


def _f(name, default):
    return float(os.getenv(name, default))


class Settings:
    database_url = os.getenv("DATABASE_URL", "sqlite:///./forestwatch_dev.db")
    jwt_secret = os.getenv("JWT_SECRET", "")
    jwt_expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))
    cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
    image_dir = os.getenv("IMAGE_DIR", "./data/images")

    sh_provider = os.getenv("SH_PROVIDER", "cdse").lower()
    sh_client_id = os.getenv("SH_CLIENT_ID", "")
    sh_client_secret = os.getenv("SH_CLIENT_SECRET", "")
    gfw_api_key = os.getenv("GFW_API_KEY", "")

    ndvi_forest_min = _f("NDVI_FOREST_MIN", 0.60)
    ndvi_loss_max = _f("NDVI_LOSS_MAX", 0.35)
    ndvi_drop_min = _f("NDVI_DROP_MIN", 0.25)
    ndvi_uncertain_drop = _f("NDVI_UNCERTAIN_DROP", 0.15)
    nbr_burn_drop = _f("NBR_BURN_DROP", 0.27)
    burn_max_nir = _f("BURN_MAX_NIR", 0.18)
    min_patch_pixels = int(os.getenv("MIN_PATCH_PIXELS", "8"))
    max_cloud = _f("MAX_CLOUD_COVER", 30)

    alert_min_ha = _f("ALERT_MIN_HA", 1)
    sev_medium = _f("SEV_MEDIUM_HA", 10)
    sev_high = _f("SEV_HIGH_HA", 50)
    sev_critical = _f("SEV_CRITICAL_HA", 200)
    tick_minutes = int(os.getenv("SCHEDULER_TICK_MINUTES", "30"))

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    smtp_from = os.getenv("SMTP_FROM", "alerts@forestwatch.local")

    @property
    def sh_configured(self):
        return bool(self.sh_client_id and self.sh_client_secret)

    @property
    def sh_base(self):
        return "https://sh.dataspace.copernicus.eu" if self.sh_provider == "cdse" else "https://services.sentinel-hub.com"

    @property
    def sh_token_url(self):
        if self.sh_provider == "cdse":
            return "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        return "https://services.sentinel-hub.com/auth/realms/main/protocol/openid-connect/token"


settings = Settings()
