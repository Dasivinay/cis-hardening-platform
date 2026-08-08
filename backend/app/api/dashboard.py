from flask_restx import Namespace, Resource
from flask_jwt_extended import jwt_required

from app.services.dashboard_service import DashboardService

ns = Namespace("dashboard", description="Aggregate analytics & trends")


@ns.route("/summary")
class Summary(Resource):
    @jwt_required()
    def get(self):
        return DashboardService().summary()


@ns.route("/trend/<string:container_id>")
class Trend(Resource):
    @jwt_required()
    def get(self, container_id):
        return {"container_id": container_id, "trend": DashboardService().trend_for_container(container_id)}
