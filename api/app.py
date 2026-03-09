import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, request

from api.db import db
from api.models import CallRecord

load_dotenv()

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    @app.post("/end-of-call")
    def end_of_call():
        # Accept an empty body - missing fields will just be stored as NULL
        data = request.get_json(silent=True) or {}

        # appointment_date is sent as an ISO 8601 string by the agent
        raw_date = data.get("appointment_date")
        appointment_date = datetime.fromisoformat(raw_date) if raw_date else None

        record = CallRecord(
            room_id=data.get("room_id", ""),
            caller_identity=data.get("caller_identity"),
            appointment_date=appointment_date,
        )
        db.session.add(record)
        db.session.commit()

        logger.info("Call record saved: id=%s room=%s", record.id, record.room_id)
        return jsonify(record.to_dict()), 201

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
