from app.models.scan import Scan, ScheduledScan
from app.models.control import Control, ScanResultControl
from app.repositories.base_repository import BaseRepository


class ScanRepository(BaseRepository):
    model = Scan

    def list_for_container(self, container_id: str):
        return Scan.query.filter_by(container_id=container_id).order_by(Scan.created_at.desc())


class ScheduledScanRepository(BaseRepository):
    model = ScheduledScan


class ControlRepository(BaseRepository):
    model = Control

    def get_by_rule_id(self, rule_id: str):
        return Control.query.filter_by(rule_id=rule_id).first()


class ScanResultControlRepository(BaseRepository):
    model = ScanResultControl

    def list_for_scan(self, scan_id: str):
        return ScanResultControl.query.filter_by(scan_id=scan_id)
