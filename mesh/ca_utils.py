"""Minimal CA for mesh: generate CA, sign CSR."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def ensure_ca(key_path: Path, cert_path: Path) -> tuple[bytes, bytes]:
    """Ensure CA key and cert exist; create if not. Returns (ca_private_pem, ca_cert_pem)."""
    if key_path.exists() and cert_path.exists():
        return key_path.read_bytes(), cert_path.read_bytes()

    key_path.parent.mkdir(parents=True, exist_ok=True)
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "DADM Mesh CA"),
        x509.NameAttribute(NameOID.COMMON_NAME, "mesh-ca"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(priv.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .sign(priv, hashes.SHA256(), default_backend())
    )
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    key_path.write_bytes(priv_pem)
    cert_path.write_bytes(cert_pem)
    return priv_pem, cert_pem


def sign_csr(csr_pem: bytes, ca_priv_pem: bytes, ca_cert_pem: bytes) -> bytes:
    """Sign CSR with CA; return signed certificate PEM."""
    csr = x509.load_pem_x509_csr(csr_pem, default_backend())
    ca_priv = serialization.load_pem_private_key(ca_priv_pem, password=None, backend=default_backend())
    ca_cert = x509.load_pem_x509_certificate(ca_cert_pem, default_backend())

    cert = (
        x509.CertificateBuilder()
        .subject_name(csr.subject)
        .issuer_name(ca_cert.subject)
        .public_key(csr.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))
        .sign(ca_priv, hashes.SHA256(), default_backend())
    )
    return cert.public_bytes(serialization.Encoding.PEM)
