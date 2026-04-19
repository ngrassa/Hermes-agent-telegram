#!/bin/bash
# ============================================================
#  deploy.sh — Déploie l'app sur EC2 après terraform apply
#  Usage : ./deploy.sh
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/terraform"
APP_DIR="$SCRIPT_DIR/app"

# ── Récupération des outputs Terraform ───────────────────────
echo "📋 Récupération des infos de déploiement..."
cd "$TERRAFORM_DIR"

EC2_IP=$(terraform output -raw ec2_public_ip)
KEY_FILE="${HOME}/Downloads/labsuser.pem"

# Vérification que la clé vockey existe
if [ ! -f "$KEY_FILE" ]; then
  echo "❌ Clé vockey introuvable : $KEY_FILE"
  echo "   → Learner Lab > AWS Details > Download PEM → labsuser.pem"
  echo "   Puis : chmod 400 ~/Downloads/labsuser.pem"
  exit 1
fi
chmod 400 "$KEY_FILE"
S3_BUCKET=$(terraform output -raw s3_bucket_name)
AWS_REGION=$(terraform output -raw ec2_public_ip > /dev/null 2>&1; terraform -chdir=. output -json | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('aws_region',{}).get('value','us-east-1'))" 2>/dev/null || echo "us-east-1")

SSH_CMD="ssh -i $KEY_FILE -o StrictHostKeyChecking=no ec2-user@$EC2_IP"

echo "🌐 IP EC2 : $EC2_IP"
echo "🪣 Bucket S3 : $S3_BUCKET"

# ── Attente que l'instance soit prête ────────────────────────
echo "⏳ Attente que l'instance soit accessible (max 3 min)..."
for i in $(seq 1 36); do
  if $SSH_CMD "test -f /var/log/bootstrap.status" 2>/dev/null; then
    echo "✅ Instance prête !"
    break
  fi
  if [ "$i" -eq 36 ]; then
    echo "❌ Timeout : l'instance ne répond pas après 3 minutes."
    exit 1
  fi
  printf "."
  sleep 5
done

# ── Upload des documents vers S3 ─────────────────────────────
DOCS_DIR="$SCRIPT_DIR/docs"
if [ -d "$DOCS_DIR" ] && [ "$(ls -A $DOCS_DIR 2>/dev/null)" ]; then
  echo "📤 Upload des documents vers S3..."
  aws s3 sync "$DOCS_DIR/" "s3://$S3_BUCKET/docs/" --region us-east-1
  echo "✅ Documents uploadés"
else
  echo "⚠️  Aucun document dans ./docs/ — ajoute tes fichiers .txt/.md puis relance."
fi

# ── Copie de l'application sur EC2 ───────────────────────────
echo "📦 Déploiement de l'application..."
$SSH_CMD "mkdir -p /opt/hermes-bot"
scp -i "$KEY_FILE" -o StrictHostKeyChecking=no \
    "$APP_DIR/bot.py" \
    "ec2-user@$EC2_IP:/tmp/bot.py"

$SSH_CMD "sudo cp /tmp/bot.py /opt/hermes-bot/bot.py && sudo chown botuser:botuser /opt/hermes-bot/bot.py"

# ── Synchronisation docs S3 -> EC2 ───────────────────────────
echo "📥 Synchronisation des docs S3 vers l'instance..."
$SSH_CMD "aws s3 sync s3://$S3_BUCKET/docs/ /opt/hermes-bot/docs/ --region us-east-1 || echo 'Pas de docs S3'"

# ── Démarrage / Redémarrage du service ───────────────────────
echo "🚀 Démarrage du service hermes-bot..."
$SSH_CMD "sudo systemctl enable hermes-bot && sudo systemctl restart hermes-bot"

sleep 3
STATUS=$($SSH_CMD "sudo systemctl is-active hermes-bot" 2>/dev/null || echo "unknown")
if [ "$STATUS" = "active" ]; then
  echo ""
  echo "╔══════════════════════════════════════════════╗"
  echo "║  ✅  Hermes RAG Bot déployé avec succès !   ║"
  echo "╚══════════════════════════════════════════════╝"
  echo ""
  echo "📡 Voir les logs en direct :"
  echo "   $SSH_CMD 'sudo journalctl -u hermes-bot -f'"
  echo ""
  echo "🔄 Recharger les docs après ajout :"
  echo "   aws s3 sync ./docs/ s3://$S3_BUCKET/docs/"
  echo "   Puis tape /reload dans ton bot Telegram"
else
  echo "❌ Le service ne semble pas actif (status: $STATUS)"
  echo "   Vérifiez les logs : $SSH_CMD 'sudo journalctl -u hermes-bot -n 50'"
  exit 1
fi
