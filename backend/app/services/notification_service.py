from app.extensions import db
from app.models.notification import Notification
from app.utils.errors import NotFoundError


class NotificationService:
    def notify(self, user_id: str, title: str, message: str = None, level: str = "info"):
        notif = Notification(user_id=user_id, title=title, message=message, level=level)
        db.session.add(notif)
        db.session.commit()
        return notif

    def list_for_user(self, user_id: str, unread_only: bool = False):
        query = Notification.query.filter_by(user_id=user_id)
        if unread_only:
            query = query.filter_by(is_read=False)
        return query.order_by(Notification.created_at.desc())

    def mark_read(self, user_id: str, notification_id: str):
        notif = Notification.query.filter_by(id=notification_id, user_id=user_id).first()
        if not notif:
            raise NotFoundError("Notification not found.")
        notif.is_read = True
        db.session.commit()
        return notif

    def mark_all_read(self, user_id: str):
        Notification.query.filter_by(user_id=user_id, is_read=False).update({"is_read": True})
        db.session.commit()
