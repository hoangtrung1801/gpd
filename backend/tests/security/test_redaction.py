import pytest
from gpd.audit.service import AuditService, append as append_audit
from gpd.db.engine import Database
from gpd.security.redaction import Redactor, redact


@pytest.fixture
def redactor() -> Redactor:
    return Redactor()


def test_redactor_removes_common_secret_formats(redactor: Redactor):
    result = redactor.redact("token=sk-example1234567890 and xoxb-123-456-secret")
    assert "sk-example" not in result.text
    assert "xoxb-" not in result.text
    assert result.redaction_count == 2


def test_redactor_removes_github_tokens(redactor: Redactor):
    result = redactor.redact(
        "Old token: ghp_1234567890abcdef1234567890, fine-grained: github_pat_11AEXAMPLE_secret1234567890"
    )
    assert "ghp_1234" not in result.text
    assert "github_pat_" not in result.text
    assert result.redaction_count == 2


def test_redactor_removes_pem_blocks(redactor: Redactor):
    pem = """-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Y1+examplePrivateData
-----END RSA PRIVATE KEY-----"""
    result = redactor.redact(f"Config:\n{pem}\nEnd of config")
    assert "examplePrivateData" not in result.text
    assert "-----BEGIN" not in result.text
    assert result.redaction_count == 1


def test_redactor_removes_authorization_headers(redactor: Redactor):
    result = redactor.redact(
        "Request: Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and Authorization: Basic dXNlcjpwYXNz"
    )
    assert "eyJhbGci" not in result.text
    assert "dXNlcjpwYXNz" not in result.text
    assert result.redaction_count == 2


def test_redactor_removes_dotenv_secrets(redactor: Redactor):
    dotenv = """GPD_ACCESS_TOKEN="supersecret12345"
DATABASE_URL=postgres://user:pass@localhost/db
GPD_SLACK_SIGNING_SECRET=slack_secret_value_99
SAFE_VAR=hello_world
"""
    result = redactor.redact(dotenv)
    assert "supersecret12345" not in result.text
    assert "slack_secret_value_99" not in result.text
    assert "hello_world" in result.text
    assert result.redaction_count >= 2


def test_redactor_custom_patterns():
    custom_redactor = Redactor(patterns=[r"MY_SECRET_\d+"])
    result = custom_redactor.redact("Here is MY_SECRET_42 and sk-example1234567890")
    assert "MY_SECRET_42" not in result.text
    assert "sk-example" not in result.text
    assert result.redaction_count == 2


def test_redact_data_recursively():
    r = Redactor()
    data = {
        "token": "sk-example1234567890",
        "nested": {
            "auth": "Authorization: Bearer test_bearer_token",
            "items": ["xoxb-123-456-secret", "safe_string"],
        },
    }
    redacted = r.redact_data(data)
    assert "sk-example" not in redacted["token"]
    assert "test_bearer_token" not in redacted["nested"]["auth"]
    assert "xoxb-" not in redacted["nested"]["items"][0]
    assert redacted["nested"]["items"][1] == "safe_string"


def test_audit_service_redacts_before_persistence(database: Database):
    with database.connect() as conn:
        with conn.begin():
            event = append_audit(
                conn,
                "sk-example1234567890",
                "login",
                "xoxb-123-456-secret",
                {"api_key": "sk-example1234567890", "details": "normal action"},
            )

    assert "sk-example" not in event.actor
    assert "xoxb-" not in event.target
    assert "sk-example" not in str(event.metadata)

    # Verify directly from database
    svc = AuditService(database)
    persisted = svc.get(event.id)
    assert persisted is not None
    assert "sk-example" not in persisted.actor
    assert "xoxb-" not in persisted.target
    assert "sk-example" not in (persisted.metadata or "")
