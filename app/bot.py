"""
================================================================
  Hermes RAG Telegram Bot
  Agent RAG avec Nous-Hermes-2 via Groq API + ChromaDB
  Communication : python-telegram-bot (polling)
================================================================
"""

import os
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Telegram
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# LangChain RAG
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader,
    UnstructuredMarkdownLoader,
    DirectoryLoader,
)
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

load_dotenv()

# ── Configuration ─────────────────────────────────────────────
TELEGRAM_TOKEN   = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_API_KEY     = os.environ["GROQ_API_KEY"]
CHROMA_DIR       = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
DOCS_DIR         = os.getenv("DOCS_LOCAL_DIR", "./docs")
EMBED_MODEL      = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL        = "nous-hermes-llama2-13b"  # Hermes-2 sur Groq
MAX_HISTORY_TURNS = 5

# ── Prompt système Hermes ─────────────────────────────────────
SYSTEM_PROMPT = """<|im_start|>system
Tu es un assistant intelligent et précis basé sur Nous-Hermes-2.
Tu réponds UNIQUEMENT à partir des documents fournis dans le contexte.
Si la réponse n'est pas dans les documents, dis-le clairement et honnêtement.
Réponds en français, de façon structurée et concise.
<|im_end|>

Contexte extrait de la base de connaissances :
{context}

Historique de la conversation :
{chat_history}

<|im_start|>user
{question}
<|im_end|>
<|im_start|>assistant"""

CONDENSE_PROMPT = """<|im_start|>system
Reformule la question de suivi en une question autonome et claire.
<|im_end|>

Historique : {chat_history}
Question de suivi : {question}
Question autonome :<|im_end|>"""

# ── Classe principale du bot ──────────────────────────────────
class HermesRAGBot:
    def __init__(self):
        self.vectorstore = None
        self.embeddings = None
        self.llm = None
        # Mémoire par utilisateur (user_id -> Memory)
        self.user_memories: dict[int, ConversationBufferWindowMemory] = {}

    def initialize_rag(self) -> bool:
        """Charge les documents, crée les embeddings et la vectorstore."""
        logger.info("Initialisation du pipeline RAG...")

        # Modèle d'embeddings léger (local, pas de coût API)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

        chroma_path = Path(CHROMA_DIR)
        docs_path   = Path(DOCS_DIR)

        # Si la vectorstore existe déjà sur disque, on la charge
        if chroma_path.exists() and any(chroma_path.iterdir()):
            logger.info("Chargement vectorstore existante depuis %s", CHROMA_DIR)
            self.vectorstore = Chroma(
                persist_directory=str(chroma_path),
                embedding_function=self.embeddings,
            )
        else:
            # Chargement et indexation des documents
            if not docs_path.exists() or not any(docs_path.iterdir()):
                logger.warning("Aucun document trouvé dans %s", DOCS_DIR)
                return False

            logger.info("Chargement des documents depuis %s", DOCS_DIR)
            loader_cls = {
                "**/*.txt": TextLoader,
                "**/*.md":  UnstructuredMarkdownLoader,
            }
            all_docs = []
            for pattern, cls in loader_cls.items():
                loader = DirectoryLoader(
                    str(docs_path),
                    glob=pattern,
                    loader_cls=cls,
                    show_progress=True,
                )
                all_docs.extend(loader.load())

            if not all_docs:
                logger.warning("Aucun fichier .txt/.md trouvé")
                return False

            logger.info("%d document(s) chargé(s), découpage en chunks...", len(all_docs))
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=800,
                chunk_overlap=100,
                length_function=len,
            )
            chunks = splitter.split_documents(all_docs)
            logger.info("%d chunks créés, vectorisation...", len(chunks))

            chroma_path.mkdir(parents=True, exist_ok=True)
            self.vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=str(chroma_path),
            )
            logger.info("Vectorstore persistée dans %s", CHROMA_DIR)

        # LLM Groq — Nous-Hermes-2
        self.llm = ChatGroq(
            model=LLM_MODEL,
            api_key=GROQ_API_KEY,
            temperature=0.3,
            max_tokens=1024,
        )
        logger.info("Pipeline RAG initialisé avec succès.")
        return True

    def get_chain(self, user_id: int) -> ConversationalRetrievalChain:
        """Retourne une chaîne RAG avec mémoire isolée par utilisateur."""
        if user_id not in self.user_memories:
            self.user_memories[user_id] = ConversationBufferWindowMemory(
                k=MAX_HISTORY_TURNS,
                memory_key="chat_history",
                return_messages=False,
                output_key="answer",
            )

        qa_prompt = PromptTemplate(
            input_variables=["context", "chat_history", "question"],
            template=SYSTEM_PROMPT,
        )
        condense_prompt = PromptTemplate(
            input_variables=["chat_history", "question"],
            template=CONDENSE_PROMPT,
        )

        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vectorstore.as_retriever(
                search_type="mmr",          # Maximal Marginal Relevance
                search_kwargs={"k": 4, "fetch_k": 10},
            ),
            memory=self.user_memories[user_id],
            combine_docs_chain_kwargs={"prompt": qa_prompt},
            condense_question_prompt=condense_prompt,
            return_source_documents=True,
            verbose=False,
        )

    async def query(self, user_id: int, question: str) -> str:
        """Interroge la chaîne RAG et retourne la réponse formatée."""
        if not self.vectorstore or not self.llm:
            return "⚠️ La base de connaissances n'est pas encore chargée. Réessaie dans quelques instants."

        try:
            chain  = self.get_chain(user_id)
            result = await asyncio.to_thread(chain.invoke, {"question": question})
            answer = result.get("answer", "Je n'ai pas trouvé de réponse.")

            # Ajout des sources (noms de fichiers uniquement)
            sources = result.get("source_documents", [])
            source_names = list({
                Path(doc.metadata.get("source", "")).name
                for doc in sources
                if doc.metadata.get("source")
            })
            if source_names:
                answer += "\n\n📄 *Sources :* " + ", ".join(f"`{s}`" for s in source_names)

            return answer
        except Exception as e:
            logger.error("Erreur RAG pour user %d : %s", user_id, e, exc_info=True)
            return f"❌ Erreur lors de la recherche : {type(e).__name__}"


# ── Instance globale ──────────────────────────────────────────
bot = HermesRAGBot()


# ── Handlers Telegram ─────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await update.message.reply_text(
        f"👋 Bonjour *{user.first_name}* !\n\n"
        "Je suis *Hermes*, ton assistant RAG alimenté par Nous-Hermes-2.\n\n"
        "📚 Pose-moi n'importe quelle question sur la base de connaissances.\n"
        "🔄 Tape /reset pour effacer l'historique de notre conversation.\n"
        "ℹ️ Tape /status pour vérifier l'état du système.",
        parse_mode="Markdown",
    )


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    bot.user_memories.pop(user_id, None)
    await update.message.reply_text("🗑️ Historique effacé. Nouvelle conversation !")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if bot.vectorstore:
        count = bot.vectorstore._collection.count()
        status = (
            f"✅ *Système opérationnel*\n\n"
            f"🔢 Chunks indexés : *{count}*\n"
            f"🤖 Modèle LLM : `{LLM_MODEL}`\n"
            f"🧠 Embeddings : `all-MiniLM-L6-v2`\n"
            f"🗂️ Vectorstore : ChromaDB (persistant)"
        )
    else:
        status = "⚠️ *Base de connaissances non initialisée.* Vérifie les logs."
    await update.message.reply_text(status, parse_mode="Markdown")


async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recharge la vectorstore depuis le dossier docs (admin uniquement)."""
    await update.message.reply_text("♻️ Rechargement de la base... (peut prendre 1-2 min)")
    import shutil
    shutil.rmtree(CHROMA_DIR, ignore_errors=True)
    success = await asyncio.to_thread(bot.initialize_rag)
    if success:
        await update.message.reply_text("✅ Base rechargée avec succès !")
    else:
        await update.message.reply_text("❌ Échec du rechargement. Vérifie que des docs sont présents dans /docs.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id  = update.effective_user.id
    question = update.message.text

    # Indicateur de frappe pendant la génération
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing",
    )

    answer = await bot.query(user_id, question)
    await update.message.reply_text(answer, parse_mode="Markdown")


# ── Point d'entrée ────────────────────────────────────────────
def main() -> None:
    logger.info("Démarrage de Hermes RAG Bot...")

    # Initialisation RAG (bloquant au démarrage)
    success = bot.initialize_rag()
    if not success:
        logger.warning("Bot démarré sans vectorstore — /reload pour charger des docs.")

    # Construction de l'application Telegram
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("reload", cmd_reload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot en écoute (polling)...")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
