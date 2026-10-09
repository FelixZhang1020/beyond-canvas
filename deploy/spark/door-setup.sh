#!/bin/sh
# Make the Spark's door once: a certificate authority, a certificate for the public address,
# the class password and the cookie key. Re-running keeps whatever already exists, so the
# password changes only when its file is removed. Run on the node; start.sh runs it.
#
# The certificate is our own (operator decision: a one-time browser warning rather
# than a plain address, because on a plain address the browser withholds the camera and the
# microphone the class page needs). An iPad trusts it once ca.crt is installed from
# https://<address>/door/certificate and switched on under Settings > General > About >
# Certificate Trust Settings. 180 days stays inside Apple's 398-day limit and outlasts the
# contest.
#
# The extensions go through a small config file rather than -addext, which the Mac's
# /usr/bin/openssl (LibreSSL) does not take; the node has OpenSSL 3.0.
set -eu
DIR=${BEYOND_CANVAS_DOOR_DIR:-$HOME/.config/beyond-canvas/door}
PUBLIC=${BEYOND_CANVAS_PUBLIC_IP:-203.0.113.10}
umask 077
mkdir -p "$DIR"
chmod 700 "$DIR"
cd "$DIR"
printf '%s\n' '[req]' 'distinguished_name = dn' 'prompt = no' 'x509_extensions = authority' \
    '[dn]' 'CN = Beyond Canvas classroom door' \
    '[authority]' 'basicConstraints = critical,CA:TRUE' 'keyUsage = critical,keyCertSign,cRLSign' \
    'subjectKeyIdentifier = hash' > door.cnf
printf '%s\n' "subjectAltName = IP:$PUBLIC,IP:127.0.0.1,DNS:localhost" 'extendedKeyUsage = serverAuth' \
    'basicConstraints = CA:FALSE' 'keyUsage = critical,digitalSignature,keyEncipherment' \
    'subjectKeyIdentifier = hash' 'authorityKeyIdentifier = keyid' > server.ext
if [ ! -f ca.key ]; then
    openssl req -x509 -newkey rsa:2048 -nodes -sha256 -days 180 -config door.cnf -keyout ca.key -out ca.crt 2>/dev/null
fi
if [ ! -f server.crt ]; then
    openssl req -new -newkey rsa:2048 -nodes -config door.cnf -subj "/CN=$PUBLIC" -keyout server.key -out server.csr 2>/dev/null
    openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days 180 -sha256 \
        -extfile server.ext -out server.leaf 2>/dev/null
    cat server.leaf ca.crt > server.crt
    rm -f server.csr server.leaf
fi
rm -f door.cnf server.ext
[ -f key ] || python3 -c "import secrets, sys; sys.stdout.buffer.write(secrets.token_bytes(32))" > key
if [ ! -f password ]; then
    python3 -c "import secrets; a = 'abcdefghjkmnpqrstuvwxyz23456789'; print('-'.join(''.join(secrets.choice(a) for _ in range(4)) for _ in range(3)))" > password
    echo "a new class password is in $DIR/password"
fi
chmod 600 ca.key server.key key password
