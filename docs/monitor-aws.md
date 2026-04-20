# Agent de Monitoring AWS — Hermes Bot (ISET Sousse)

## Description générale

Script Python de monitoring AWS déployé sur EC2 Ubuntu.
Il surveille les instances EC2, les coûts AWS, et intègre un assistant pédagogique
Linux + RAG Kubernetes via Groq API. Interface : Telegram (@ngrassa_bot).

## Architecture du système

- Langage : Python 3
- Déploiement : EC2 Ubuntu, service systemd aws-monitor
- LLM : llama3-70b-8192 via Groq API
- Embeddings : paraphrase-multilingual-MiniLM-L12-v2 (SentenceTransformer)
- Vectorstore : FAISS (en mémoire) + cache JSON
- Source RAG : PDF du livre Kubernetes du Pr. Grassa
- Interface : Telegram Bot (polling)
- AWS SDK : boto3 (EC2 + Cost Explorer)

## Dépendances Python

- boto3 : SDK AWS (EC2, Cost Explorer)
- requests : appels API Telegram
- groq : client Groq API
- PyMuPDF (fitz) : extraction texte PDF
- sentence-transformers : embeddings multilingues
- faiss-cpu : recherche vectorielle
- numpy : calcul similarité cosinus

Installation : pip3 install boto3 requests groq PyMuPDF sentence-transformers faiss-cpu numpy

## Variables d'environnement (fichier /etc/aws-monitor.env)

- TELEGRAM_TOKEN : token du bot Telegram (BotFather)
- TELEGRAM_CHAT_ID : chat_id de l'administrateur
- AWS_REGION : région AWS (défaut us-east-1)
- BUDGET_DAILY_LIMIT : seuil d'alerte coût journalier en dollars (défaut 3)
- BUDGET_MONTHLY_LIMIT : seuil d'alerte coût mensuel en dollars (défaut 30)
- GROQ_API_KEY : clé API Groq pour le LLM

## Commandes Telegram disponibles

### Alertes AWS
- /start : s'abonner aux alertes automatiques
- /stop : se désabonner des alertes
- /status : afficher l'état de toutes les instances EC2
- /abonnes : lister les étudiants abonnés (admin uniquement)

### Assistant pédagogique Linux
- /linux <question> : expliquer une commande Linux avec exemple pratique
- Question libre sans commande : détection automatique du sujet

### RAG Livre Kubernetes (Pr. Grassa)
- /kube <question> : interroger le livre Kubernetes par recherche sémantique
- /reset : effacer l'historique de conversation
- /help : afficher toutes les commandes

## Fonctionnalités de monitoring AWS

### Surveillance des instances EC2
- Détection automatique des changements d'état (running, stopped, terminated)
- Alerte Telegram immédiate si une instance change d'état
- Vérification toutes les 5 minutes via boto3 describe_instances

### Surveillance des coûts AWS
- Coût journalier via AWS Cost Explorer (get_cost_and_usage)
- Coût mensuel cumulé
- Alerte si dépassement du seuil journalier ou mensuel
- Rapport quotidien automatique à 8h du matin

### Système d'abonnés
- Stockage des chat_id dans /home/ubuntu/subscribers.json
- Broadcast automatique à l'admin + tous les abonnés
- Gestion subscribe/unsubscribe par commande Telegram

## Pipeline RAG Kubernetes

### Indexation du PDF
1. Extraction du texte page par page avec PyMuPDF
2. Découpe en chunks de 400-450 caractères avec chevauchement de 50 caractères
3. Vectorisation avec SentenceTransformer paraphrase-multilingual-MiniLM-L12-v2
4. Cache de l'index dans /home/ubuntu/kube_index.json pour éviter re-calcul
5. Chargement au démarrage en thread daemon

### Recherche et génération
1. Vectorisation de la question avec le même modèle
2. Calcul de similarité cosinus entre question et tous les chunks
3. Sélection des 3 chunks les plus pertinents (top_k=3)
4. Seuil minimum de score : 0.25 (sinon réponse "non trouvé")
5. Injection des chunks dans le prompt Groq avec numéros de page
6. Génération avec llama3-70b-8192, température 0.3, max 700 tokens

### Détection automatique Kubernetes
Mots-clés déclencheurs : kubernetes, kubectl, pod, deployment, service,
ingress, namespace, node, cluster, container, docker, helm, configmap,
secret, pvc, volume, k8s, minikube, k3s, replicaset, statefulset,
daemonset, job, cronjob, rbac, manifest, yaml, orchestration, scaling

## Assistant Linux pédagogique

### Format de réponse imposé
Pour chaque commande Linux demandée :
1. Explication simple en 1-2 phrases
2. Syntaxe de base
3. Exemple concret et pratique
4. Erreur courante à éviter

### Gestion de la mémoire conversationnelle
- Historique par chat_id stocké en mémoire (dictionnaire Python)
- Fenêtre glissante de 10 derniers échanges
- Commande /reset pour effacer l'historique
- Modèle : llama3-70b-8192, température 0.4, max 600 tokens

## Service systemd

Fichier : /etc/systemd/system/aws-monitor.service
Utilisateur : ubuntu
Redémarrage automatique : oui (RestartSec=15)
Logs : journalctl -u aws-monitor -f
Activation : systemctl enable aws-monitor && systemctl start aws-monitor

## Déploiement

### Prérequis sur l'instance EC2
- Ubuntu (pas Amazon Linux)
- Python 3 + pip3
- Rôle IAM avec accès EC2 (describe) et Cost Explorer (get_cost_and_usage)
- Port sortant 443 ouvert (HTTPS vers Telegram et Groq)

### Upload du livre Kubernetes
scp kubernetes_book.pdf ubuntu@<IP>:/home/ubuntu/
sudo systemctl restart aws-monitor

### Commandes utiles
- Voir les logs : sudo journalctl -u aws-monitor -f
- Redémarrer : sudo systemctl restart aws-monitor
- Statut : sudo systemctl status aws-monitor
- Effacer le cache RAG : rm /home/ubuntu/kube_index.json && sudo systemctl restart aws-monitor

## Différences avec le bot Hermes RAG principal

| Critère | Hermes RAG (ce projet) | Agent Monitor AWS |
|---------|----------------------|-------------------|
| OS | Amazon Linux 2023 | Ubuntu |
| Vectorstore | ChromaDB persistant | FAISS en mémoire |
| Source docs | Fichiers .txt/.md S3 | PDF Kubernetes local |
| LLM | llama-3.1-8b-instant | llama3-70b-8192 |
| Monitoring AWS | Non | Oui (EC2 + coûts) |
| Abonnés | Non | Oui (multi-utilisateurs) |
| Rapport quotidien | Non | Oui (8h du matin) |
