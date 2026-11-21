---
name: linux-essentials
description: Skill per amministrazione Linux (comandi, filesystem, processi, utenti, permessi, rete, scripting) derivata dal materiale LPI Linux Essentials. Usa quando l'utente chiede comandi Linux o amministrazione sistema.
---

# Linux Essentials — skill per amministrazione Linux (LPI)

Flusso: **contesto → comando → verifica**.

## 1. Scopo

- Comandi Linux essenziali (file, processi, utenti, rete, pacchetti).
- Concetti LPI: filesystem hierarchy, permessi, shell, scripting base.

## 2. Comandi file e directory

```bash
ls -la
cd /path
pwd
mkdir -p dir/sub
cp -r src dst
mv old new
rm -rf dir
find / -name "*.conf" 2>/dev/null
```

## 3. Permessi e utenti

```bash
chmod 755 file
chown user:group file
useradd -m -s /bin/bash nuovo
passwd nuovo
groups user
sudo -u user comando
```

## 4. Processi e servizi

```bash
ps aux
top
kill -9 PID
systemctl status nginx
systemctl restart nginx
journalctl -u nginx -f
```

## 5. Rete

```bash
ip addr
ip route
ss -tulpn
ping -c 4 8.8.8.8
curl -I https://example.com
```

## 6. Pacchetti

```bash
# Debian/Ubuntu
apt update && apt install -y pkg
# RHEL/CentOS
dnf install -y pkg
# Arch
pacman -S pkg
```

## 7. Shell e scripting

```bash
#!/bin/bash
set -euo pipefail
for f in *.txt; do echo "$f"; done
```

## 8. Quality gates

- Mai `rm -rf /` o path non verificati.
- Usare `set -euo pipefail` negli script.
- Verificare con `--dry-run` quando disponibile.
