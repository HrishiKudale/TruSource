# models/rfid_models.py
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class RFIDRecord(db.Model):
    __tablename__ = "rfid_records"

    id = db.Column(db.Integer, primary_key=True)

    crop_id = db.Column(db.String(128), nullable=False, index=True)
    user_id = db.Column(db.String(128), nullable=False, index=True)

    username = db.Column(db.String(255), nullable=False)
    crop_type = db.Column(db.String(255), nullable=False)

    packaging_date = db.Column(db.String(64), nullable=False)
    expiry_date = db.Column(db.String(64), nullable=False)
    bag_capacity = db.Column(db.String(64), nullable=False)
    total_bags = db.Column(db.String(64), nullable=False)

    rfid_epc = db.Column(db.String(256), nullable=False, index=True)

    tx_hash = db.Column(db.String(128), nullable=True, index=True)
    status = db.Column(db.String(32), nullable=False, default="PENDING")  # PENDING | MINED | FAILED
    error_message = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("crop_id", "rfid_epc", name="uq_rfid_crop_epc"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "crop_id": self.crop_id,
            "user_id": self.user_id,
            "username": self.username,
            "crop_type": self.crop_type,
            "packaging_date": self.packaging_date,
            "expiry_date": self.expiry_date,
            "bag_capacity": self.bag_capacity,
            "total_bags": self.total_bags,
            "rfid_epc": self.rfid_epc,
            "tx_hash": self.tx_hash,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
# backend/rfid_models.py
from dataclasses import dataclass
from typing import List

@dataclass
class RFIDRegisterPayload:
    userId: str
    username: str
    cropType: str
    cropId: str
    packagingDate: str
    expiryDate: str
    bagCapacity: str
    totalBags: str
    epcs: List[str]
