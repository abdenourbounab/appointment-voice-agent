from datetime import datetime, timezone

from api.db import db


class CallRecord(db.Model):
    __tablename__ = "call_records"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_id = db.Column(db.String(255), nullable=False)
    caller_identity = db.Column(db.String(255), nullable=True)
    appointment_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "room_id": self.room_id,
            "caller_identity": self.caller_identity,
            "appointment_date": self.appointment_date.isoformat() if self.appointment_date else None,
            "created_at": self.created_at.isoformat(),
        }
