# 🤖 Hermes RAG Telegram Bot — AWS Academy

Agent conversationnel RAG (Retrieval-Augmented Generation) déployé sur AWS EC2, propulsé par **Nous-Hermes-2** via **Groq API**, avec interface **Telegram**.

---

## 🏗️ Architecture

```
Utilisateur Telegram
       ↕ polling
  Telegram Bot API
       ↓
  EC2 t3.large (us-east-1)
  ┌─────────────────────────────────┐
  │  python-telegram-bot (handler)  │
  │           ↓                     │
  │   LangChain RAG Agent           │◄──► Groq API (Nous-Hermes-2)
  │           ↓                     │
  │     ChromaDB (local)            │
  │           ↑                     │
  │   Doc Loader (.txt/.md)         │◄──── S3 Bucket (sources)
  └─────────────────────────────────┘
```

---

## ⚡ Prérequis

| Outil | Version | Lien |
|-------|---------|------|
| Terraform | ≥ 1.3 | https://developer.hashicorp.com/terraform/install |
| AWS CLI | v2 | configuré avec les credentials AWS Academy |
| Python | 3.11 | pour tests locaux |
| Token Telegram | — | créé via @BotFather |
| Clé Groq API | — | https://console.groq.com/keys |

---

## 🚀 Déploiement en 5 étapes

### 1. Configurer les credentials AWS Academy

Dans le Learner Lab AWS Academy :
```bash
# Copie les credentials depuis "AWS Details" > "AWS CLI"
mkdir -p ~/.aws
cat > ~/.aws/credentials << 'EOF'
[default]
aws_access_key_id = ASIA...
aws_secret_access_key = ...
aws_session_token = ...
EOF
```

> ⚠️ Les credentials AWS Academy expirent toutes les 4h. Renouvelle-les si tu as des erreurs d'auth.

### 2. Configurer les variables Terraform

```bash
cd terraform/
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars   # remplis telegram_bot_token et groq_api_key
```

### 3. Ajouter tes documents

```bash
# Copie tes fichiers .txt et .md dans :
cp /chemin/vers/tes/docs/*.md docs/
cp /chemin/vers/tes/docs/*.txt docs/
```

### 4. Provisionner l'infrastructure

```bash
cd terraform/
terraform init
terraform plan      # vérifie ce qui va être créé
terraform apply     # tape "yes" pour confirmer
```

Outputs attendus :
```
ec2_public_ip    = "54.x.x.x"
s3_bucket_name   = "hermes-rag-bot-docs-a1b2c3d4"
ssh_command      = "ssh -i ../hermes-rag-bot-key.pem ec2-user@54.x.x.x"
```

### 5. Déployer l'application

```bash
cd ..   # retour à la racine du projet
chmod +x deploy.sh
./deploy.sh
```

---

## 💬 Commandes Telegram

| Commande | Description |
|----------|-------------|
| `/start` | Message de bienvenue |
| `/status` | État du système (nb de chunks, modèle) |
| `/reset` | Efface l'historique de conversation |
| `/reload` | Recharge la base depuis S3 (après ajout de docs) |
| (message libre) | Question à l'agent RAG |

---

## 🔄 Mettre à jour les documents

```bash
# 1. Ajoute tes nouveaux fichiers dans ./docs/
# 2. Upload vers S3
aws s3 sync ./docs/ s3://$(cd terraform && terraform output -raw s3_bucket_name)/docs/
# 3. Tape /reload dans ton bot Telegram pour reindexer
```

---

## 🔍 Debugging

```bash
# Voir les logs en direct
ssh -i hermes-rag-bot-key.pem ec2-user@<IP> 'sudo journalctl -u hermes-bot -f'

# Redémarrer le bot
ssh -i hermes-rag-bot-key.pem ec2-user@<IP> 'sudo systemctl restart hermes-bot'

# Se connecter à l'instance
ssh -i hermes-rag-bot-key.pem ec2-user@<IP>

# Voir le log du bootstrap
ssh -i hermes-rag-bot-key.pem ec2-user@<IP> 'cat /var/log/user-data.log'
```

---

## 🧹 Nettoyage (éviter les frais)

```bash
cd terraform/
terraform destroy   # supprime TOUTES les ressources AWS
```

---

## 📁 Structure du projet

```
hermes-rag-telegram/
├── terraform/
│   ├── main.tf                   # EC2, SG, IAM, S3, keypair
│   ├── variables.tf              # Variables
│   ├── outputs.tf                # Outputs post-apply
│   ├── terraform.tfvars.example  # Template de config
│   └── user_data.sh.tpl          # Bootstrap EC2
├── app/
│   └── bot.py                    # Agent RAG + Telegram
├── docs/
│   └── exemple-guide.md          # Tes fichiers .txt/.md ici
├── deploy.sh                     # Script de déploiement
└── README.md
```

---

## ⚠️ Notes AWS Academy

- **Région** : utilise toujours `us-east-1` (les autres peuvent avoir des restrictions)
- **IAM** : AWS Academy ne permet pas de créer des utilisateurs IAM — le rôle EC2 est utilisé à la place
- **Credentials** : expire toutes les 4h, renouvelle depuis le Learner Lab
- **Session Token** : obligatoire dans `~/.aws/credentials` pour AWS Academy
- **Keypair Terraform** : la clé `.pem` est générée automatiquement par Terraform avec le provider `tls`
