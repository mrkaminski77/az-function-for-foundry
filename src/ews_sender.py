import json
import logging
import os
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from exchangelib import (
    Account,
    Configuration,
    DELEGATE,
    IMPERSONATION,
    Mailbox,
    Message,
    OAUTH2,
    OAuth2Credentials,
)


def _is_truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _get_required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable '{name}'")
    return value


def _get_required_secret(client: SecretClient, secret_name: str) -> str:
    secret = client.get_secret(secret_name)
    value = (secret.value or "").strip()
    if not value:
        raise ValueError(f"Secret '{secret_name}' is empty in Key Vault")
    return value


def _resolve_access_type() -> str:
    configured = os.getenv("EWS_ACCESS_TYPE", "IMPERSONATION").strip().upper()
    return IMPERSONATION if configured == "IMPERSONATION" else DELEGATE


def _build_email_body(source_key: str, results: list[dict[str, Any]]) -> str:
    summary = {
        "sourceKey": source_key,
        "totalItems": len(results),
        "successful": sum(1 for item in results if (item.get("classification") or {}).get("ok") is True),
        "failed": sum(1 for item in results if (item.get("classification") or {}).get("ok") is False),
    }
    payload = {
        "summary": summary,
        "items": results,
    }
    return json.dumps(payload, indent=2)


def send_results_via_ews(source_key: str, results: list[dict[str, Any]]) -> None:
    if not _is_truthy(os.getenv("EWS_SEND_RESULTS_ENABLED", "false")):
        logging.info("EWS sending disabled. Set EWS_SEND_RESULTS_ENABLED=true to enable result emails.")
        return

    vault_url = _get_required_env("KEY_VAULT_URL")
    tenant_id = _get_required_env("EWS_TENANT_ID")
    sender_email = _get_required_env("EWS_SENDER_EMAIL")
    recipients_raw = _get_required_env("EWS_RECIPIENTS")
    client_id_secret_name = _get_required_env("EWS_CLIENT_ID_SECRET_NAME")
    client_secret_secret_name = _get_required_env("EWS_CLIENT_SECRET_SECRET_NAME")

    recipients = [
        Mailbox(email_address=value.strip())
        for value in recipients_raw.split(",")
        if value.strip()
    ]
    if not recipients:
        raise ValueError("EWS_RECIPIENTS did not contain any valid email addresses")

    credential = DefaultAzureCredential()
    key_vault_client = SecretClient(vault_url=vault_url, credential=credential)

    client_id = _get_required_secret(key_vault_client, client_id_secret_name)
    client_secret = _get_required_secret(key_vault_client, client_secret_secret_name)

    ews_server = os.getenv("EWS_SERVER", "outlook.office365.com").strip()
    subject_prefix = os.getenv("EWS_SUBJECT_PREFIX", "[OCDS]").strip()

    oauth_credentials = OAuth2Credentials(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
    )
    configuration = Configuration(
        server=ews_server,
        credentials=oauth_credentials,
        auth_type=OAUTH2,
    )
    account = Account(
        primary_smtp_address=sender_email,
        config=configuration,
        autodiscover=False,
        access_type=_resolve_access_type(),
    )

    message = Message(
        account=account,
        folder=account.sent,
        subject=f"{subject_prefix} Classification results for {source_key}",
        body=_build_email_body(source_key=source_key, results=results),
        to_recipients=recipients,
    )
    message.send_and_save()
    logging.info(
        "EWS results email sent. source=%s recipients=%d totalItems=%d",
        source_key,
        len(recipients),
        len(results),
    )
