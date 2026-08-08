from unittest.mock import patch, MagicMock


def test_create_container_requires_docker(client, admin_token):
    """
    Without a real Docker daemon in the test environment, DockerService.create_target
    should surface a clean ExternalServiceError (502) rather than crash the process —
    verifying our error boundary, not real Docker behavior (covered by integration tests).
    """
    resp = client.post(
        "/api/v1/containers",
        json={"name": "target-x"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code in (502, 201)  # 201 only if a real Docker daemon is reachable


@patch("app.services.docker_service.docker.from_env")
def test_create_container_mocked_docker(mock_from_env, client, admin_token):
    mock_client = MagicMock()
    mock_container = MagicMock()
    mock_container.id = "abc123"
    mock_client.containers.run.return_value = mock_container
    mock_from_env.return_value = mock_client

    resp = client.post(
        "/api/v1/containers",
        json={"name": "target-mocked"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "target-mocked"
    assert body["docker_container_id"] == "abc123"
