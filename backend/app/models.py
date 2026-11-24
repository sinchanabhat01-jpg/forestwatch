from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, Text, ForeignKey, JSON, Index, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(190), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(100))
    notify_email: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class MonitoredLocation(Base):
    __tablename__ = "monitored_locations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    west: Mapped[float] = mapped_column(Float)
    south: Mapped[float] = mapped_column(Float)
    east: Mapped[float] = mapped_column(Float)
    north: Mapped[float] = mapped_column(Float)
    area_ha: Mapped[float] = mapped_column(Float)
    monitoring_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency_days: Mapped[int] = mapped_column(Integer, default=7)
    monitoring_status: Mapped[str] = mapped_column(String(40), default="idle")
    monitoring_message: Mapped[str | None] = mapped_column(String(400), nullable=True)
    latest_observation: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_analysis_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    analyses = relationship("DeforestationAnalysis", back_populates="location", cascade="all, delete-orphan", passive_deletes=True)


class SatelliteImage(Base):
    __tablename__ = "satellite_images"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("monitored_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(40))
    acquisition_from: Mapped[date] = mapped_column(Date)
    acquisition_to: Mapped[date] = mapped_column(Date)
    cloud_cover_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_pixel_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    bbox: Mapped[list] = mapped_column(JSON)
    file_path: Mapped[str] = mapped_column(String(300))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DeforestationAnalysis(Base):
    __tablename__ = "deforestation_analysis"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("monitored_locations.id", ondelete="CASCADE"), nullable=True, index=True)
    before_image_id: Mapped[int | None] = mapped_column(ForeignKey("satellite_images.id", ondelete="SET NULL"), nullable=True)
    after_image_id: Mapped[int | None] = mapped_column(ForeignKey("satellite_images.id", ondelete="SET NULL"), nullable=True)
    bbox: Mapped[list] = mapped_column(JSON)
    place_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    before_date: Mapped[date] = mapped_column(Date)
    after_date: Mapped[date] = mapped_column(Date)
    method: Mapped[str] = mapped_column(String(60), default="ndvi-rules-v1")
    thresholds: Mapped[dict] = mapped_column(JSON)
    mean_ndvi_before: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_ndvi_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    forest_area_ha: Mapped[float] = mapped_column(Float, default=0)
    loss_ha: Mapped[float] = mapped_column(Float, default=0)
    uncertain_ha: Mapped[float] = mapped_column(Float, default=0)
    fire_ha: Mapped[float] = mapped_column(Float, default=0)
    loss_pct_of_forest: Mapped[float] = mapped_column(Float, default=0)
    valid_pixel_pct: Mapped[float] = mapped_column(Float, default=0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    report_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    overlay_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    location = relationship("MonitoredLocation", back_populates="analyses")
    __table_args__ = (Index("ix_analysis_user_created", "user_id", "created_at"),)


class DeforestationAlert(Base):
    __tablename__ = "deforestation_alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("deforestation_analysis.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("monitored_locations.id", ondelete="SET NULL"), nullable=True, index=True)
    location_name: Mapped[str] = mapped_column(String(200))
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    detection_date: Mapped[date] = mapped_column(Date)
    loss_ha: Mapped[float] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(12), default="NEW", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AnalysisHistory(Base):
    """Audit log of user actions: comparisons, detections, monitoring checks, reviews."""
    __tablename__ = "analysis_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    analysis_id: Mapped[int | None] = mapped_column(ForeignKey("deforestation_analysis.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
