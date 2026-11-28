#!/usr/bin/env python3
"""SumaiBoard offsite backup encryption (spec 7.2).

PBKDF2-HMAC-SHA256 (480k iterations, random 16B salt) derives a Fernet key.
The plaintext payload is: 8-byte big-endian manifest length + manifest bytes +
archive bytes. The payload is split into 4 MiB chunks; every chunk's Fernet
plaintext internally binds backup_id, archive name, chunk index and total
chunk count, so chunks cannot be mixed across generations, replaced or
reordered. Memory use is bounded (<64 MiB) regardless of archive size:
encryption streams chunk by chunk and decryption (M-03-R1) authenticates
and writes chunk by chunk to temp files, atomically publishing the result
only after every chunk, the total length and the exact EOF are verified.
"""
import argparse
import base64
import hashlib
import json
import os
import struct
import sys

from cryptography.fernet import Fernet, InvalidToken

CHUNK = 4 * 1024 * 1024
ITERATIONS = 480_000


def derive_key(passphrase: bytes, salt: bytes) -> bytes:
    key = hashlib.pbkdf2_hmac("sha256", passphrase, salt, ITERATIONS, dklen=32)
    return base64.urlsafe_b64encode(key)


def read_passphrase(path: str) -> bytes:
    with open(path, "rb") as fh:
        return fh.read().strip()


def encrypt(archive_path: str, manifest_path: str, out_path: str,
            passphrase_file: str, backup_id: str) -> None:
    passphrase = read_passphrase(passphrase_file)
    salt = os.urandom(16)
    fernet = Fernet(derive_key(passphrase, salt))
    manifest = open(manifest_path, "rb").read()
    archive_name = os.path.basename(archive_path)
    payload_size = 8 + len(manifest) + os.path.getsize(archive_path)
    total_chunks = max(1, (payload_size + CHUNK - 1) // CHUNK)
    header = {
        "format": "sumaiboard-backup-crypto-v1",
        "kdf": "PBKDF2-HMAC-SHA256",
        "iterations": ITERATIONS,
        "salt_b64": base64.b64encode(salt).decode("ascii"),
        "chunk_size": CHUNK,
        "chunks": total_chunks,
        "backup_id": backup_id,
        "archive": archive_name,
    }
    with open(archive_path, "rb") as archive, open(out_path, "wb") as out:
        out.write(json.dumps(header).encode("utf-8") + b"\n")

        def payload_stream():
            yield struct.pack(">Q", len(manifest))
            yield manifest
            while True:
                data = archive.read(CHUNK)
                if not data:
                    break
                yield data

        buffer = b""
        index = 0
        for piece in payload_stream():
            buffer += piece
            while len(buffer) >= CHUNK:
                chunk, buffer = buffer[:CHUNK], buffer[CHUNK:]
                _write_chunk(out, fernet, backup_id, archive_name, index, total_chunks, chunk)
                index += 1
        if buffer or index == 0:
            _write_chunk(out, fernet, backup_id, archive_name, index, total_chunks, buffer)
            index += 1
        if index != total_chunks:
            raise SystemExit(f"chunk count mismatch: wrote {index}, header says {total_chunks}")


def _write_chunk(out, fernet, backup_id, archive, index, total, data):
    binding = json.dumps({
        "backup_id": backup_id, "archive": archive, "index": index, "total": total,
    }).encode("utf-8")
    token = fernet.encrypt(binding + b"\n" + data)
    out.write(struct.pack(">Q", len(token)))
    out.write(token)


def decrypt(enc_path: str, out_archive: str, out_manifest: str,
            passphrase_file: str, expect_backup_id: str = "") -> dict:
    """Streaming decrypt (M-03-R1).

    Authenticates and writes chunk by chunk. Peak memory is bounded by one
    chunk plus the (size-capped) manifest; the archive is never accumulated
    in memory. Token length, manifest length and chunk count are validated
    before data is trusted. Results are written to temp files in the
    destination directory and atomically renamed only after every chunk,
    the total payload length and the exact end-of-file position verify;
    any failure removes the temp outputs.
    """
    MAX_TOKEN = CHUNK * 2
    MAX_MANIFEST = 16 * 1024 * 1024
    MAX_CHUNKS = 100000
    passphrase = read_passphrase(passphrase_file)
    out_dir = os.path.dirname(os.path.abspath(out_archive)) or "."
    tmp_archive = os.path.join(out_dir, ".dec-archive.tmp")
    tmp_manifest = os.path.join(out_dir, ".dec-manifest.tmp")
    try:
        with open(enc_path, "rb") as fh:
            header = json.loads(fh.readline().decode("utf-8"))
            if header.get("format") != "sumaiboard-backup-crypto-v1":
                raise SystemExit("unknown backup crypto format")
            if int(header.get("chunk_size", 0)) != CHUNK:
                raise SystemExit("unexpected chunk_size in header")
            total = int(header["chunks"])
            if total < 1 or total > MAX_CHUNKS:
                raise SystemExit("chunk count out of bounds")
            fernet = Fernet(derive_key(passphrase, base64.b64decode(header["salt_b64"])))
            if expect_backup_id and header["backup_id"] != expect_backup_id:
                raise SystemExit("backup_id mismatch in header")
            manifest_len = None
            manifest_buf = bytearray()
            prefix_buf = bytearray()
            archive_bytes = 0
            with open(tmp_archive, "wb") as archive_out:
                for index in range(total):
                    raw_len = fh.read(8)
                    if len(raw_len) != 8:
                        raise SystemExit(f"truncated chunk header at {index}")
                    (token_len,) = struct.unpack(">Q", raw_len)
                    if token_len < 1 or token_len > MAX_TOKEN:
                        raise SystemExit(f"chunk {index} token length out of bounds")
                    token = fh.read(token_len)
                    if len(token) != token_len:
                        raise SystemExit(f"truncated chunk at {index}")
                    try:
                        plain = fernet.decrypt(token)
                    except InvalidToken:
                        raise SystemExit(f"chunk {index} authentication failed")
                    binding_line, _, data = plain.partition(b"\n")
                    binding = json.loads(binding_line.decode("utf-8"))
                    if (binding["backup_id"] != header["backup_id"]
                            or binding["archive"] != header["archive"]
                            or binding["index"] != index or binding["total"] != total):
                        raise SystemExit(f"chunk {index} binding mismatch")
                    view = data
                    if manifest_len is None:
                        prefix_buf += view
                        if len(prefix_buf) < 8:
                            continue
                        (manifest_len,) = struct.unpack(">Q", bytes(prefix_buf[:8]))
                        if manifest_len < 0 or manifest_len > MAX_MANIFEST:
                            raise SystemExit("manifest length out of bounds")
                        view = bytes(prefix_buf[8:])
                        prefix_buf = bytearray()
                    if manifest_len is not None and len(manifest_buf) < manifest_len:
                        take = min(manifest_len - len(manifest_buf), len(view))
                        manifest_buf += view[:take]
                        view = view[take:]
                    if view:
                        archive_out.write(view)
                        archive_bytes += len(view)
                if fh.read(1):
                    raise SystemExit("trailing data after final chunk")
            if manifest_len is None or len(manifest_buf) != manifest_len:
                raise SystemExit("payload shorter than declared manifest")
            if archive_bytes <= 0:
                raise SystemExit("empty archive payload")
        with open(tmp_manifest, "wb") as fh:
            fh.write(bytes(manifest_buf))
        os.replace(tmp_manifest, out_manifest)
        os.replace(tmp_archive, out_archive)
    except BaseException:
        for p in (tmp_archive, tmp_manifest):
            try:
                os.unlink(p)
            except OSError:
                pass
        raise
    return header


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    enc = sub.add_parser("encrypt")
    enc.add_argument("--archive", required=True)
    enc.add_argument("--manifest", required=True)
    enc.add_argument("--out", required=True)
    enc.add_argument("--passphrase-file", required=True)
    enc.add_argument("--backup-id", required=True)
    dec = sub.add_parser("decrypt")
    dec.add_argument("--in", dest="inp", required=True)
    dec.add_argument("--out-archive", required=True)
    dec.add_argument("--out-manifest", required=True)
    dec.add_argument("--passphrase-file", required=True)
    dec.add_argument("--backup-id", default="")
    args = parser.parse_args()
    if args.cmd == "encrypt":
        encrypt(args.archive, args.manifest, args.out, args.passphrase_file, args.backup_id)
    else:
        header = decrypt(args.inp, args.out_archive, args.out_manifest,
                         args.passphrase_file, args.backup_id)
        print(json.dumps({"backup_id": header["backup_id"], "archive": header["archive"],
                          "chunks": header["chunks"]}))


if __name__ == "__main__":
    main()
