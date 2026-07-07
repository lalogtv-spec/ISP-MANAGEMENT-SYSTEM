"""Minimal WebAuthn helpers for phone biometric/passkey enrollment and verification."""
from __future__ import annotations

import base64
import hashlib
import json
import struct

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _decode_length(data: bytes, index: int, additional_info: int):
    if additional_info < 24:
        return additional_info, index
    if additional_info == 24:
        return data[index], index + 1
    if additional_info == 25:
        return struct.unpack(">H", data[index:index + 2])[0], index + 2
    if additional_info == 26:
        return struct.unpack(">I", data[index:index + 4])[0], index + 4
    if additional_info == 27:
        return struct.unpack(">Q", data[index:index + 8])[0], index + 8
    raise ValueError("Indefinite CBOR lengths are not supported here")


def _decode_cbor(data: bytes, index: int = 0):
    if index >= len(data):
        raise ValueError("Unexpected end of CBOR data")

    initial = data[index]
    index += 1
    major_type = initial >> 5
    additional_info = initial & 0x1F

    if major_type in (0, 1):
        value, index = _decode_length(data, index, additional_info)
        if major_type == 1:
            value = -1 - value
        return value, index

    if major_type == 2:
        length, index = _decode_length(data, index, additional_info)
        value = data[index:index + length]
        return value, index + length

    if major_type == 3:
        length, index = _decode_length(data, index, additional_info)
        value = data[index:index + length].decode("utf-8")
        return value, index + length

    if major_type == 4:
        length, index = _decode_length(data, index, additional_info)
        value = []
        for _ in range(length):
            item, index = _decode_cbor(data, index)
            value.append(item)
        return value, index

    if major_type == 5:
        length, index = _decode_length(data, index, additional_info)
        value = {}
        for _ in range(length):
            key, index = _decode_cbor(data, index)
            item, index = _decode_cbor(data, index)
            value[key] = item
        return value, index

    if major_type == 6:
        _, index = _decode_length(data, index, additional_info)
        return _decode_cbor(data, index)

    if major_type == 7:
        if additional_info in (20, 21, 22):
            return {20: False, 21: True, 22: None}[additional_info], index
        if additional_info == 23:
            return None, index
        if additional_info == 24:
            return data[index], index + 1
        if additional_info == 25:
            return struct.unpack(">e", data[index:index + 2])[0], index + 2
        if additional_info == 26:
            return struct.unpack(">f", data[index:index + 4])[0], index + 4
        if additional_info == 27:
            return struct.unpack(">d", data[index:index + 8])[0], index + 8
        if additional_info == 31:
            raise ValueError("Indefinite length values are not supported")
        return additional_info, index

    raise ValueError(f"Unsupported CBOR major type: {major_type}")


def decode_cbor(data: bytes):
    value, index = _decode_cbor(data, 0)
    if index != len(data):
        raise ValueError("Trailing CBOR data detected")
    return value


def parse_client_data(client_data_json: bytes):
    payload = json.loads(client_data_json.decode("utf-8"))
    challenge = payload.get("challenge", "")
    origin = payload.get("origin", "")
    return payload, challenge, origin


def parse_authenticator_data(auth_data: bytes):
    if len(auth_data) < 37:
        raise ValueError("Authenticator data is too short")

    rp_id_hash = auth_data[:32]
    flags = auth_data[32]
    sign_count = struct.unpack(">I", auth_data[33:37])[0]
    cursor = 37
    attested_credential_data = None

    if flags & 0x40:
        if len(auth_data) < cursor + 18:
            raise ValueError("Attested credential data is incomplete")
        aaguid = auth_data[cursor:cursor + 16]
        cursor += 16
        credential_id_length = struct.unpack(">H", auth_data[cursor:cursor + 2])[0]
        cursor += 2
        credential_id = auth_data[cursor:cursor + credential_id_length]
        cursor += credential_id_length
        cose_public_key, cursor = _decode_cbor(auth_data, cursor)
        attested_credential_data = {
            "aaguid": aaguid,
            "credential_id": credential_id,
            "cose_public_key": cose_public_key,
        }

    return {
        "rp_id_hash": rp_id_hash,
        "flags": flags,
        "sign_count": sign_count,
        "attested_credential_data": attested_credential_data,
        "raw": auth_data,
    }


def cose_key_to_public_key(cose_key: dict):
    kty = cose_key.get(1)
    alg = cose_key.get(3)
    crv = cose_key.get(-1)
    x = cose_key.get(-2)
    y = cose_key.get(-3)

    if kty != 2 or alg != -7 or crv != 1 or not isinstance(x, (bytes, bytearray)) or not isinstance(y, (bytes, bytearray)):
        raise ValueError("Unsupported WebAuthn public key")

    public_numbers = ec.EllipticCurvePublicNumbers(
        int.from_bytes(x, "big"),
        int.from_bytes(y, "big"),
        ec.SECP256R1(),
    )
    return public_numbers.public_key()


def verify_webauthn_assertion(public_key, authenticator_data: bytes, client_data_json: bytes, signature: bytes):
    client_hash = hashlib.sha256(client_data_json).digest()
    signed_data = authenticator_data + client_hash

    signature_to_verify = signature
    if len(signature) == 64:
        r = int.from_bytes(signature[:32], 'big')
        s = int.from_bytes(signature[32:], 'big')
        signature_to_verify = asym_utils.encode_dss_signature(r, s)

    public_key.verify(signature_to_verify, signed_data, ec.ECDSA(hashes.SHA256()))

