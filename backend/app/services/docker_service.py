"""
Docker orchestration service.

SECURITY BOUNDARY: every method in this class operates only against containers
that this platform created and tracks in the `containers` table. There is no
method here that accepts an arbitrary host command outside that scope, and the
platform process itself is never targeted by exec calls.
"""
import docker
from docker.errors import NotFound, APIError
from flask import current_app

from app.repositories.container_repository import ContainerRepository
from app.utils.errors import NotFoundError, ConflictError, ExternalServiceError


class DockerService:
    def __init__(self):
        self.repo = ContainerRepository()
        self._client = None

    @property
    def client(self):
        if self._client is None:
            try:
                self._client = docker.from_env()
            except Exception as exc:
                raise ExternalServiceError(f"Could not connect to Docker daemon: {exc}")
        return self._client

    def _resolve_network(self) -> str | None:
        """
        Returns the configured DOCKER_NETWORK name only if it actually exists
        on the Docker daemon; otherwise falls back to None (default bridge).
        Guards against a misconfigured/renamed Compose project producing a
        network name that doesn't exist, which would otherwise make every
        `create_target` call fail with a 404 from the Docker API.
        """
        network_name = current_app.config.get("DOCKER_NETWORK")
        if not network_name:
            return None
        try:
            self.client.networks.get(network_name)
            return network_name
        except NotFound:
            current_app.logger.warning(
                f"Configured DOCKER_NETWORK='{network_name}' does not exist on the "
                f"Docker daemon; creating target on the default bridge network instead."
            )
            return None

    def create_target(self, name: str, created_by_id: str, image: str | None = None):
        if self.repo.get_by_name(name):
            raise ConflictError(f"A target named '{name}' already exists.")

        image = image or current_app.config["DOCKER_TARGET_IMAGE"]
        docker_name = f"cis-target-{name}"

        # Self-heal from a previous run's orphan: the DB row can be gone
        # (e.g. a crashed request that created the container but never
        # persisted the record, or a manually-deleted DB row) while the
        # Docker daemon still holds a container with this name. Without this
        # check `containers.run(name=...)` fails with a raw 409 from the
        # Docker API, which is exactly the unhandled-Docker-exception /
        # duplicate-name case callers need automatic recovery from, not a
        # traceback surfaced to the user.
        try:
            existing = self.client.containers.get(docker_name)
        except NotFound:
            existing = None
        except APIError as exc:
            raise ExternalServiceError(f"Could not reach Docker to check for existing target containers: {exc}")

        if existing is not None:
            existing.reload()
            if existing.status == "running":
                raise ConflictError(
                    f"A Docker container named '{docker_name}' is already running but is not tracked by "
                    f"this platform (likely an orphan from a previous session). Stop and remove it manually, "
                    f"or choose a different target name."
                )
            current_app.logger.warning(
                f"docker.orphan_container_removed name={docker_name} status={existing.status} "
                f"(untracked container with a colliding name; removing before creating the new target)"
            )
            try:
                existing.remove(force=True)
            except APIError as exc:
                raise ExternalServiceError(
                    f"Found a stale, untracked container named '{docker_name}' but could not remove it: {exc}"
                )

        try:
            container = self.client.containers.run(
                image,
                name=docker_name,
                detach=True,
                tty=True,
                network=self._resolve_network(),
                labels={"managed-by": "cis-platform"},
            )
        except docker.errors.ImageNotFound:
            raise ExternalServiceError(
                f"Image '{image}' not found locally. Run: docker compose build scan-target-image-builder"
            )
        except APIError as exc:
            raise ExternalServiceError(f"Docker error creating target: {exc}")

        from app.models.container import Container
        record = Container(
            name=name,
            docker_container_id=container.id,
            image=image,
            status="running",
            created_by_id=created_by_id,
        )
        return self.repo.add(record)

    def ensure_current_image(self, container_record_id: str) -> bool:
        """
        Detects and self-heals "stale target" drift: a tracked container was
        created from an OLDER build of its image tag (e.g. the target image
        was rebuilt after a content/config fix — such as the CPE_NAME fix in
        targets/ubuntu-scan-target/Dockerfile — but this specific container
        instance predates that rebuild and never got replaced).

        This is not hypothetical: `containers.run()` snapshots whatever the
        image tag resolves to *at creation time*. Rebuilding the image later
        (docker compose build ...) never touches containers already running
        from the old image layers — Docker has no mechanism to retroactively
        update them. Without this check, a target created before a fix keeps
        silently scanning against the old container forever, producing
        real, well-formed reports that legitimately score 0 passed / 0
        failed / N/A — indistinguishable from a genuine parsing bug, with no
        diagnostic trail pointing at "your container is stale." That is
        exactly the failure mode that let this bug survive multiple rounds
        of otherwise-correct scoring/parser fixes.

        Called before every scan. If drift is detected, transparently
        replaces the container (same tracked name, fresh image) and updates
        the DB record in place, so the scan that follows always runs against
        the current image. Returns True if a recreation happened.
        """
        record = self._get_tracked(container_record_id)

        try:
            current_image = self.client.images.get(record.image)
        except NotFound:
            raise ExternalServiceError(
                f"Target image '{record.image}' no longer exists locally. "
                f"Run: docker compose build scan-target-image-builder"
            )
        except APIError as exc:
            raise ExternalServiceError(f"Could not reach Docker to check target image freshness: {exc}")

        try:
            handle = self.client.containers.get(record.docker_container_id)
            handle.reload()
        except NotFound:
            handle = None
        except APIError as exc:
            raise ExternalServiceError(f"Could not reach Docker to inspect target container: {exc}")

        # attrs['Image'] is the image ID the container was actually created
        # from — this stays frozen even after the tag is rebuilt to point at
        # a new image ID. Comparing it to the tag's *current* resolved ID is
        # what catches the drift.
        container_image_id = handle.attrs.get("Image") if handle else None

        if handle is not None and container_image_id == current_image.id:
            return False  # already fresh — nothing to do

        docker_name = handle.name if handle is not None else f"cis-target-{record.name}"
        if handle is not None:
            current_app.logger.warning(
                f"docker.target_image_stale name={docker_name} "
                f"container_image={container_image_id} current_image={current_image.id} "
                f"(recreating container from the current image before scanning)"
            )
            try:
                handle.remove(force=True)
            except APIError as exc:
                raise ExternalServiceError(f"Could not remove stale target container '{docker_name}': {exc}")
        else:
            current_app.logger.warning(
                f"docker.target_container_missing name={docker_name} "
                f"(tracked container no longer exists in Docker; recreating from current image)"
            )

        try:
            new_container = self.client.containers.run(
                record.image,
                name=docker_name,
                detach=True,
                tty=True,
                network=self._resolve_network(),
                labels={"managed-by": "cis-platform"},
            )
        except APIError as exc:
            raise ExternalServiceError(f"Docker error recreating stale target container: {exc}")

        record.docker_container_id = new_container.id
        record.status = "running"
        self.repo.add(record)
        current_app.logger.info(
            f"docker.target_recreated name={docker_name} new_container_id={new_container.id}"
        )
        return True

    def _get_tracked(self, container_record_id: str):
        record = self.repo.get_by_id(container_record_id)
        if not record:
            raise NotFoundError("Target container not found.")
        return record

    def _docker_handle(self, record):
        try:
            return self.client.containers.get(record.docker_container_id)
        except NotFound:
            record.status = "error"
            self.repo.add(record)
            raise NotFoundError("Underlying Docker container no longer exists.")
        except APIError as exc:
            raise ExternalServiceError(f"Docker error while accessing target container: {exc}")

    def start(self, container_record_id: str):
        record = self._get_tracked(container_record_id)
        handle = self._docker_handle(record)
        handle.start()
        return self.repo.update(record, status="running")

    def stop(self, container_record_id: str):
        record = self._get_tracked(container_record_id)
        handle = self._docker_handle(record)
        handle.stop(timeout=10)
        return self.repo.update(record, status="stopped")

    def restart(self, container_record_id: str):
        record = self._get_tracked(container_record_id)
        handle = self._docker_handle(record)
        handle.restart(timeout=10)
        return self.repo.update(record, status="running")

    def delete(self, container_record_id: str):
        record = self._get_tracked(container_record_id)
        try:
            handle = self.client.containers.get(record.docker_container_id)
            handle.remove(force=True)
        except NotFound:
            pass
        except APIError as exc:
            raise ExternalServiceError(f"Docker error removing target container: {exc}")
        self.repo.delete(record)

    def logs(self, container_record_id: str, tail: int = 200) -> str:
        record = self._get_tracked(container_record_id)
        handle = self._docker_handle(record)
        return handle.logs(tail=tail).decode("utf-8", errors="replace")

    def exec_in_target(
        self, container_record_id: str, command: list[str], timeout: int | None = None, demux: bool = False
    ):
        """
        Execute a command strictly inside a tracked target container.
        `command` must be a list (never a raw shell string) to avoid shell injection.
        `timeout` (seconds) is enforced client-side via a thread, since docker-py's
        exec_run has no native timeout parameter — a hung scan process would
        otherwise block a Celery worker indefinitely.

        By default (`demux=False`) returns `(exit_code, output)` where `output`
        is a single merged stdout+stderr string, preserving the original
        contract every existing caller (and test) relies on. Pass
        `demux=True` to instead get `(exit_code, (stdout, stderr))` as two
        separately decoded strings -- used for the real oscap invocation so
        its stdout/stderr can be captured and stored independently rather
        than interleaved.
        """
        record = self._get_tracked(container_record_id)
        handle = self._docker_handle(record)

        def _run_once():
            return handle.exec_run(command, demux=demux)

        if timeout is None:
            result = _run_once()
        else:
            import threading
            result_holder = {}

            def _run():
                try:
                    result_holder["result"] = _run_once()
                except Exception as exc:  # noqa: BLE001
                    result_holder["error"] = exc

            thread = threading.Thread(target=_run, daemon=True)
            thread.start()
            thread.join(timeout)

            if thread.is_alive():
                raise ExternalServiceError(f"Command timed out after {timeout}s inside target container: {' '.join(command)}")
            if "error" in result_holder:
                raise ExternalServiceError(f"Error executing command in target container: {result_holder['error']}")
            result = result_holder["result"]

        if demux:
            stdout_raw, stderr_raw = result.output if result.output else (None, None)
            stdout = stdout_raw.decode("utf-8", errors="replace") if stdout_raw else ""
            stderr = stderr_raw.decode("utf-8", errors="replace") if stderr_raw else ""
            return result.exit_code, (stdout, stderr)

        output = result.output.decode("utf-8", errors="replace") if result.output else ""
        return result.exit_code, output

    def file_exists_in_target(self, container_record_id: str, path: str) -> tuple[bool, int]:
        """Returns (exists, size_bytes) using `stat -c %s` inside the target — used to
        confirm a report file was actually written before attempting to copy it out."""
        exit_code, output = self.exec_in_target(container_record_id, ["stat", "-c", "%s", path], timeout=15)
        if exit_code != 0:
            return False, 0
        try:
            return True, int(output.strip())
        except ValueError:
            return True, 0

    def sync_status(self, container_record_id: str):
        record = self._get_tracked(container_record_id)
        try:
            handle = self.client.containers.get(record.docker_container_id)
            handle.reload()
            self.repo.update(record, status=handle.status)
        except NotFound:
            self.repo.update(record, status="removed")
        except APIError as exc:
            current_app.logger.warning(f"docker.sync_status_failed container_id={record.docker_container_id} error={exc}")
        return record
