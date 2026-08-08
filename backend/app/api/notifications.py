from flask import request
from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from app.services.notification_service import NotificationService
from app.api._pagination import get_pagination_args, paginated_response

ns = Namespace("notifications", description="In-app notifications")


@ns.route("")
class NotificationList(Resource):
    @jwt_required()
    def get(self):
        page, per_page = get_pagination_args()
        unread_only = request.args.get("unread_only", "false").lower() == "true"
        user_id = get_jwt_identity()
        query = NotificationService().list_for_user(user_id, unread_only=unread_only)
        return paginated_response(query, page, per_page, lambda n: n.to_dict())


@ns.route("/<string:notification_id>/read")
class MarkRead(Resource):
    @jwt_required()
    def post(self, notification_id):
        user_id = get_jwt_identity()
        notif = NotificationService().mark_read(user_id, notification_id)
        return notif.to_dict()


@ns.route("/read-all")
class MarkAllRead(Resource):
    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        NotificationService().mark_all_read(user_id)
        return {"message": "All notifications marked as read."}
