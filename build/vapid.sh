#!/usr/bin/env bash
set -euo pipefail

# A fresh VAPID key pair for one instance's reminders, appended to its env file.
#   build/vapid.sh ENV_FILE [IMAGE]    IMAGE defaults to boredroom:stage
# The keys are made inside the image (it has the cryptography library) and go straight
# into the file; nothing is printed. Restart the container afterwards. Replacing a pair
# later means every device subscribes again, quietly, the next time the app is opened.

env_file="${1:?say which env file: build/vapid.sh path/to/boredroom-stage.env}"
image="${2:-boredroom:stage}"
[[ -f "$env_file" ]] || { echo "no such file: $env_file" >&2; exit 1; }
if grep -q '^BOREDROOM_VAPID_PRIVATE_KEY=.' "$env_file"; then
  echo "$env_file already has a VAPID key; remove both BOREDROOM_VAPID_ lines first to replace it" >&2; exit 1
fi
keys=$(docker run --rm --entrypoint python "$image" -c '
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
b = lambda x: base64.urlsafe_b64encode(x).rstrip(b"=").decode()
k = ec.generate_private_key(ec.SECP256R1())
print("BOREDROOM_VAPID_PUBLIC_KEY=" + b(k.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)))
print("BOREDROOM_VAPID_PRIVATE_KEY=" + b(k.private_numbers().private_value.to_bytes(32, "big")))')
sed -i '/^BOREDROOM_VAPID_\(PUBLIC\|PRIVATE\)_KEY=/d' "$env_file"
printf '\n# web push (reminders); made by build/vapid.sh. the private key is a secret\n%s\n' "$keys" >> "$env_file"
chmod 600 "$env_file"
echo "written to $env_file. restart the container to use them."
