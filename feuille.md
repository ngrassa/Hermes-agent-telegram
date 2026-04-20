bot_logs_command = "ssh -i ~/Downloads/labsuser.pem ec2-user@3.213.183.12 'sudo journalctl -u hermes-bot -f'"
ec2_public_dns = "ec2-44-201-193-147.compute-1.amazonaws.com"
elastic_ip = "3.213.183.12"
key_reminder = "Learner Lab > AWS Details > Download PEM > labsuser.pem"
s3_bucket_name = "hermes-rag-bot-docs-865ce9f4"
s3_upload_command = "aws s3 sync ~/Telegram/docs/ s3://hermes-rag-bot-docs-865ce9f4/docs/"
ssh_command = "ssh -i ~/Downloads/labsuser.pem ec2-user@3.213.183.12"


# Depuis ton WSL, upload tes fichiers .txt/.md vers S3
aws s3 sync ~/Telegram/docs/ s3://hermes-rag-bot-docs-865ce9f4/docs/

# Puis sur l'instance, synchronise et recharge
ssh -i ~/Downloads/labsuser.pem ec2-user@44.201.193.147 \
  'aws s3 sync s3://hermes-rag-bot-docs-865ce9f4/docs/ /opt/hermes-bot/docs/ --region us-east-1'


# Sync S3 -> instance (tu es déjà dessus)
aws s3 sync s3://hermes-rag-bot-docs-865ce9f4/docs/ /opt/hermes-bot/docs/ --region us-east-1

# Redémarre le bot pour recharger les docs
sudo systemctl restart hermes-bot

# Vérifie les logs
sudo journalctl -u hermes-bot -f
