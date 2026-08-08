"""
Idempotent seed script — run automatically by docker-entrypoint.sh on boot.
Creates the three default roles, an initial admin user, and a starter
remediation library so the platform is demo-ready immediately after
`docker compose up`.
"""
import os
from app import create_app
from app.extensions import db
from app.models.user import User, Role
from app.models.control import Control
from app.models.remediation import Remediation

app = create_app(os.environ.get("FLASK_ENV", "production"))


def seed_roles():
    roles = {
        "admin": "Full platform access, including user and system administration.",
        "analyst": "Can manage targets, run scans, and view all reports.",
        "viewer": "Read-only access to dashboards and reports.",
    }
    for name, desc in roles.items():
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name, description=desc))
    db.session.commit()


def seed_admin():
    admin_email = os.environ.get("SEED_ADMIN_EMAIL", "admin@secharden.local")
    admin_password = os.environ.get("SEED_ADMIN_PASSWORD", "ChangeMe123!")

    if User.query.filter_by(email=admin_email).first():
        return

    admin_role = Role.query.filter_by(name="admin").first()
    user = User(email=admin_email, full_name="Platform Administrator", role_id=admin_role.id)
    user.set_password(admin_password)
    db.session.add(user)
    db.session.commit()
    print(f"[seed] Created default admin: {admin_email} (change the password after first login)")


def seed_remediation_library():
    """A small starter library covering common categories; grows automatically
    as new controls are discovered by scans, and is editable via the API."""
    starters = [
        {
            "rule_id": "seed_ssh_disable_root_login",
            "title": "Disable SSH root login",
            "category": "SSH",
            "severity": "high",
            "summary": "Root should never be permitted to log in directly over SSH; use sudo from a named account instead.",
            "shell_commands": "sudo sed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config\nsudo systemctl restart sshd",
            "references": "CIS Ubuntu 22.04 Benchmark 5.2.10",
        },
        {
            "rule_id": "seed_ufw_enable_firewall",
            "title": "Enable UFW firewall",
            "category": "Firewall",
            "severity": "high",
            "summary": "An active host firewall should be enabled with a default-deny inbound policy.",
            "shell_commands": "sudo ufw default deny incoming\nsudo ufw default allow outgoing\nsudo ufw enable",
            "references": "CIS Ubuntu 22.04 Benchmark 3.5.1",
        },
        {
            "rule_id": "seed_password_min_length",
            "title": "Enforce minimum password length",
            "category": "Password Policy",
            "severity": "medium",
            "summary": "Passwords should meet a minimum length requirement enforced by PAM.",
            "shell_commands": "sudo sed -i 's/^# minlen.*/minlen = 14/' /etc/security/pwquality.conf",
            "references": "CIS Ubuntu 22.04 Benchmark 5.3.1",
        },
    ]

    for item in starters:
        control = Control.query.filter_by(rule_id=item["rule_id"]).first()
        if not control:
            control = Control(
                rule_id=item["rule_id"],
                title=item["title"],
                description=item["summary"],
                severity=item["severity"],
                category=item["category"],
            )
            db.session.add(control)
            db.session.flush()

        if not Remediation.query.filter_by(control_id=control.id).first():
            db.session.add(Remediation(
                control_id=control.id,
                summary=item["summary"],
                shell_commands=item["shell_commands"],
                references=item["references"],
            ))

    db.session.commit()


if __name__ == "__main__":
    with app.app_context():
        seed_roles()
        seed_admin()
        seed_remediation_library()
        print("[seed] Database seeding complete.")
