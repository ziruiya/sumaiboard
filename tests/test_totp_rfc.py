"""RFC 6238 public test vectors for backend/totp.py (spec 4.2, MFA-22 unit part).

Run: python3 -m unittest discover -s tests -v   (stdlib only)
"""
import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.totp import hotp, totp_at, verify  # noqa: E402

# RFC 6238 Appendix B seed: ASCII "12345678901234567890", SHA-1, 8-digit codes.
SEED_B32 = base64.b32encode(b"12345678901234567890").decode("ascii")
VECTORS = [
    (59, "94287082"),
    (1111111109, "07081804"),
    (1111111111, "14050471"),
    (1234567890, "89005924"),
    (2000000000, "69279037"),
    (20000000000, "65353130"),
]


class Rfc6238Vectors(unittest.TestCase):
    def test_vectors_8_digit(self):
        for t, expected in VECTORS:
            with self.subTest(t=t):
                self.assertEqual(totp_at(SEED_B32, t, digits=8), expected)

    def test_vectors_6_digit_are_truncations(self):
        for t, expected8 in VECTORS:
            with self.subTest(t=t):
                self.assertEqual(totp_at(SEED_B32, t), expected8[-6:])

    def test_verify_returns_matched_step(self):
        code = totp_at(SEED_B32, 59)
        self.assertEqual(verify(SEED_B32, code, timestamp=59), 1)
        # Same code one window later still matches step 1 via the +/-1 window,
        # and callers consume it atomically so it cannot be replayed.
        self.assertEqual(verify(SEED_B32, code, timestamp=89), 1)
        self.assertIsNone(verify(SEED_B32, code, timestamp=300))

    def test_verify_rejects_garbage(self):
        self.assertIsNone(verify(SEED_B32, "abcdef", timestamp=59))
        self.assertIsNone(verify(SEED_B32, "12345", timestamp=59))


if __name__ == "__main__":
    unittest.main()
