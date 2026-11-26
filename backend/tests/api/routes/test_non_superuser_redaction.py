"""Non-superusers never receive TACACS+/RADIUS/MAVIS secrets from config endpoints."""

import uuid

from fastapi.testclient import TestClient

from app.core.config import settings
from app.mcp_server.redact import REDACTED

API = settings.API_V1_STR


def test_non_superuser_config_preview_redacts_secrets(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    suffix = uuid.uuid4().hex[:8]
    host_secret = f"TacacsSecret-{suffix}"
    radius_secret = f"RadiusSecret-{suffix}"
    clear_pw = f"ClearPw-{suffix}"
    mavis_key = f"TEST_LDAP_PASSWD_{suffix}"
    mavis_pw = f"LdapBindPw-{suffix}"

    host_r = client.post(
        f"{API}/hosts/",
        headers=superuser_token_headers,
        json={
            "name": f"redhost-{suffix}",
            "ipv4_address": "192.0.2.88/32",
            "secret_key": host_secret,
            "radius_secret_key": radius_secret,
        },
    )
    assert host_r.status_code == 200, host_r.text
    host_id = host_r.json()["id"]

    mavis_r = client.post(
        f"{API}/mavises/",
        headers=superuser_token_headers,
        json={"mavis_key": mavis_key, "mavis_value": mavis_pw},
    )
    assert mavis_r.status_code == 200, mavis_r.text
    mavis_id = mavis_r.json()["id"]

    opt_r = client.post(
        f"{API}/configuration_options/",
        headers=superuser_token_headers,
        json={
            "name": f"redopt-{suffix}",
            "config_option": (
                f"user u_{suffix} {{\n"
                f'    password login = clear "{clear_pw}"\n'
                f'    password ms-chap = clear "{clear_pw}"\n'
                "    password pap = login\n"
                "}"
            ),
        },
    )
    assert opt_r.status_code == 200, opt_r.text
    opt_id = opt_r.json()["id"]

    try:
        # 1) /tacacs_configs/preview
        prev = client.get(
            f"{API}/tacacs_configs/preview", headers=normal_user_token_headers
        )
        assert prev.status_code == 200
        preview_text = prev.json()["data"] or ""
        for secret in (host_secret, radius_secret, clear_pw, mavis_pw):
            assert secret not in preview_text
        assert REDACTED in preview_text

        # Superuser still sees real values
        super_prev = client.get(
            f"{API}/tacacs_configs/preview", headers=superuser_token_headers
        )
        assert super_prev.status_code == 200
        assert host_secret in (super_prev.json()["data"] or "")

        # 2) /mavises/preview, /mavises/, /mavises/{id}
        mp = client.get(f"{API}/mavises/preview", headers=normal_user_token_headers)
        assert mp.status_code == 200
        assert mavis_pw not in (mp.json()["data"] or "")
        assert f'setenv {mavis_key}="{REDACTED}"' in (mp.json()["data"] or "")

        md = client.get(f"{API}/mavises/{mavis_id}", headers=normal_user_token_headers)
        assert md.status_code == 200
        assert md.json()["mavis_value"] == REDACTED

        # Search oracle on mavis_value must not leak to non-superusers
        ms = client.get(
            f"{API}/mavises/?search={mavis_pw}", headers=normal_user_token_headers
        )
        assert ms.status_code == 200
        assert ms.json()["count"] == 0

        # 3) /hosts/ and /hosts/{id}
        hd = client.get(f"{API}/hosts/{host_id}", headers=normal_user_token_headers)
        assert hd.status_code == 200
        assert hd.json()["secret_key"] == REDACTED
        assert hd.json()["radius_secret_key"] == REDACTED

        # 4) /configuration_options/ and /configuration_options/{id}
        od = client.get(
            f"{API}/configuration_options/{opt_id}",
            headers=normal_user_token_headers,
        )
        assert od.status_code == 200
        assert clear_pw not in od.json()["config_option"]
        assert REDACTED in od.json()["config_option"]

        # Search oracle on config_option must not leak to non-superusers
        os_resp = client.get(
            f"{API}/configuration_options/?search={clear_pw}",
            headers=normal_user_token_headers,
        )
        assert os_resp.status_code == 200
        assert os_resp.json()["count"] == 0
    finally:
        client.delete(f"{API}/hosts/{host_id}", headers=superuser_token_headers)
        client.delete(f"{API}/mavises/{mavis_id}", headers=superuser_token_headers)
        client.delete(
            f"{API}/configuration_options/{opt_id}", headers=superuser_token_headers
        )
