"""
Encryption and signing for federated updates.
- Updates encrypted with symmetric key K; K encrypted with server public key (decrypt only at server).
- Client signs update payload; server signs model packages.
"""

from __future__ import annotations

import hashlib
import os
from typing import Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend


def generate_keypair() -> Tuple[bytes, bytes]:
    """Returns (private_key_pem, public_key_pem)."""
    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    pub = priv.public_key()
    priv_pem = priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_pem = pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return priv_pem, pub_pem


def encrypt_for_server(plaintext: bytes, server_public_key_pem: bytes) -> bytes:
    """
    Hybrid encryption: generate ephemeral AES key, encrypt plaintext with AES-GCM,
    encrypt AES key with server's RSA public key. Returns: iv (12) + ciphertext + encrypted_key.
    Format: len(enc_key)(2 bytes) || enc_key || nonce(12) || ciphertext.
    """
    server_pub = serialization.load_pem_public_key(server_public_key_pem, backend=default_backend())
    aes_key = os.urandom(32)
    nonce = os.urandom(12)
    aesgcm = AESGCM(aes_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)
    enc_key = server_pub.encrypt(
        aes_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    # len(enc_key) as 2-byte big-endian
    out = len(enc_key).to_bytes(2, "big") + enc_key + nonce + ciphertext
    return out


def decrypt_at_server(encrypted_payload: bytes, server_private_key_pem: bytes) -> bytes:
    """Only server (Aiximius) can decrypt. Parses payload and returns plaintext."""
    server_priv = serialization.load_pem_private_key(
        server_private_key_pem, password=None, backend=default_backend()
    )
    enc_key_len = int.from_bytes(encrypted_payload[:2], "big")
    enc_key = encrypted_payload[2 : 2 + enc_key_len]
    rest = encrypted_payload[2 + enc_key_len :]
    nonce, ct = rest[:12], rest[12:]
    aes_key = server_priv.decrypt(
        enc_key,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    aesgcm = AESGCM(aes_key)
    return aesgcm.decrypt(nonce, ct, None)


def sign_payload(payload: bytes, client_private_key_pem: bytes) -> bytes:
    """Sign payload with client private key. Returns signature bytes."""
    priv = serialization.load_pem_private_key(
        client_private_key_pem, password=None, backend=default_backend()
    )
    h = hashlib.sha256(payload).digest()
    sig = priv.sign(h, padding.PKCS1v15(), hashes.SHA256())
    return sig


def verify_signature(payload: bytes, signature: bytes, public_key_pem: bytes) -> bool:
    """Verify signature with public key (client or server)."""
    try:
        pub = serialization.load_pem_public_key(public_key_pem, backend=default_backend())
        h = hashlib.sha256(payload).digest()
        pub.verify(signature, h, padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def sign_model_package(model_blob: bytes, metadata: bytes, signing_private_key_pem: bytes) -> bytes:
    """Server signs H(model_blob || metadata). Returns signature."""
    h = hashlib.sha256(model_blob + metadata).digest()
    priv = serialization.load_pem_private_key(
        signing_private_key_pem, password=None, backend=default_backend()
    )
    return priv.sign(h, padding.PKCS1v15(), hashes.SHA256())


def verify_model_package(
    model_blob: bytes, metadata: bytes, signature: bytes, signing_public_key_pem: bytes
) -> bool:
    """Client verifies model package before install."""
    return verify_signature(model_blob + metadata, signature, signing_public_key_pem)
