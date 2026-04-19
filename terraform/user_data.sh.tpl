#!/bin/bash
# ============================================================
#  Bootstrap EC2 — Hermes RAG Telegram Bot
#  Exécuté au 1er démarrage de l'instance
# ============================================================
set -euo pipefail
exec > >(tee /var/log/user-data.log | logger -t user-data) 2>&1

echo "=== [1/6] Mise à jour système ==="
dnf update -y
dnf install -y python3.11 python3.11-pip git tmux htop

python3.11 -m pip install --upgrade pip

echo "=== [2/6] Création de l'utilisateur applicatif ==="
useradd -m -s /bin/bash botuser || true
mkdir -p /opt/hermes-bot
chown botuser:botuser /opt/hermes-bot

echo "=== [3/6] Installation des dépendances Python ==="
cat > /tmp/requirements.txt << 'PYEOF'
python-telegram-bot==21.3
langchain==0.2.11
langchain-groq==0.1.9
langchain-community==0.2.10
chromadb==0.5.5
sentence-transformers==3.0.1
boto3==1.34.144
unstructured==0.14.9
markdown==3.6
tiktoken==0.7.0
PYEOF

python3.11 -m pip install -r /tmp/requirements.txt

echo "=== [4/6] Déploiement de l'application ==="
# Ecriture des variables d'environnement
cat > /opt/hermes-bot/.env << ENVEOF
TELEGRAM_BOT_TOKEN=${telegram_token}
GROQ_API_KEY=${groq_api_key}
S3_BUCKET=${s3_bucket}
AWS_REGION=${aws_region}
CHROMA_PERSIST_DIR=/opt/hermes-bot/chroma_db
DOCS_LOCAL_DIR=/opt/hermes-bot/docs
ENVEOF

chmod 600 /opt/hermes-bot/.env
chown botuser:botuser /opt/hermes-bot/.env

# Création du dossier docs local
mkdir -p /opt/hermes-bot/docs
chown botuser:botuser /opt/hermes-bot/docs

echo "=== [5/6] Téléchargement des docs depuis S3 ==="
# Attente que l'IAM role soit bien attaché
sleep 10
aws s3 sync s3://${s3_bucket}/docs/ /opt/hermes-bot/docs/ --region ${aws_region} || echo "Aucun doc S3 pour l'instant, le bot démarrera sans base."

echo "=== [6/6] Configuration du service systemd ==="
cat > /etc/systemd/system/hermes-bot.service << 'SVCEOF'
[Unit]
Description=Hermes RAG Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/hermes-bot
EnvironmentFile=/opt/hermes-bot/.env
ExecStart=/usr/bin/python3.11 /opt/hermes-bot/bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
# Le bot sera démarré après que l'app soit copiée via deploy.sh
echo "=== Bootstrap terminé. Déployez l'app avec deploy.sh ==="
echo "BOOTSTRAP_DONE" > /var/log/bootstrap.status
