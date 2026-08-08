from croniter import croniter

from app.extensions import db
from app.repositories.scan_repository import ScheduledScanRepository
from app.repositories.container_repository import ContainerRepository
from app.utils.errors import ValidationError, NotFoundError


class SchedulingService:
    def __init__(self):
        self.repo = ScheduledScanRepository()
        self.containers = ContainerRepository()

    def _validate_cron(self, expr: str):
        if not croniter.is_valid(expr):
            raise ValidationError(f"'{expr}' is not a valid cron expression (e.g. '0 2 * * *' for daily 2am UTC).")

    def create(self, container_id: str, engine: str, benchmark_id: str, cron_expression: str, created_by_id: str):
        if not self.containers.get_by_id(container_id):
            raise NotFoundError("Target container not found.")
        self._validate_cron(cron_expression)

        from app.models.scan import ScheduledScan
        sched = ScheduledScan(
            container_id=container_id,
            engine=engine,
            benchmark_id=benchmark_id,
            cron_expression=cron_expression,
            created_by_id=created_by_id,
        )
        return self.repo.add(sched)

    def list_all(self):
        from app.models.scan import ScheduledScan
        return ScheduledScan.query.order_by(ScheduledScan.created_at.desc())

    def set_active(self, schedule_id: str, is_active: bool):
        sched = self.repo.get_by_id(schedule_id)
        if not sched:
            raise NotFoundError("Schedule not found.")
        return self.repo.update(sched, is_active=is_active)

    def delete(self, schedule_id: str):
        sched = self.repo.get_by_id(schedule_id)
        if not sched:
            raise NotFoundError("Schedule not found.")
        self.repo.delete(sched)
