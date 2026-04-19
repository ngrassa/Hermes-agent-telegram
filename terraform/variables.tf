##############################################################
#  Variables — Hermes RAG Telegram Bot
##############################################################

variable "aws_region" {
  description = "Région AWS (AWS Academy = us-east-1)"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Préfixe pour toutes les ressources"
  type        = string
  default     = "hermes-rag-bot"
}

variable "allowed_ssh_cidr" {
  description = "Ton IP publique pour l'accès SSH (ex: 197.5.12.34/32). Utilise 0.0.0.0/0 en dev."
  type        = string
  default     = "0.0.0.0/0"
}

variable "telegram_bot_token" {
  description = "Token du bot Telegram (depuis BotFather)"
  type        = string
  sensitive   = true
}

variable "groq_api_key" {
  description = "Clé API Groq (https://console.groq.com)"
  type        = string
  sensitive   = true
}
