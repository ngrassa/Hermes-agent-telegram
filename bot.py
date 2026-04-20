sudo tee /opt/hermes-bot/bot.py > /dev/null << 'BOTEOF'
"""
Hermes RAG Telegram Bot — LLaMA3.1 + ChromaDB + Groq + PDF
"""
import os, logging, asyncio, shutil
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader, DirectoryLoader, PyMuPDFLoader
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate

logging.basicConfig(format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

TELEGRAM_TOKEN    = os.environ["TELEGRAM_BOT_TOKEN"]
GROQ_API_KEY      = os.environ["GROQ_API_KEY"]
CHROMA_DIR        = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
DOCS_DIR          = os.getenv("DOCS_LOCAL_DIR", "./docs")
EMBED_MODEL       = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL         = "llama-3.1-8b-instant"
MAX_HISTORY_TURNS = 5

SYSTEM_PROMPT = """Tu es un assistant pédagogique expert en Kubernetes et DevOps.
Tu réponds à partir des documents fournis dans le contexte.
Si le contexte contient des informations partielles, complète avec tes connaissances
en précisant clairement ce qui vient du document et ce que tu ajoutes.
Réponds en français, de façon structurée et pédagogique.
Cite la page source quand tu peux.

Contexte extrait du livre :
{context}

Historique :
{chat_history}

Question : {question}
Réponse :"""

CONDENSE_PROMPT = """Reformule la question en une question autonome claire.

Historique : {chat_history}
Question : {question}
Question reformulée :"""

class HermesRAGBot:
    def __init__(self):
        self.vectorstore   = None
        self.embeddings    = None
        self.llm           = None
        self.user_memories = {}

    def initialize_rag(self) -> bool:
        logger.info("Initialisation du pipeline RAG...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        chroma_path = Path(CHROMA_DIR)
        docs_path   = Path(DOCS_DIR)

        if chroma_path.exists() and any(chroma_path.iterdir()):
            logger.info("Chargement vectorstore existante...")
            self.vectorstore = Chroma(
                persist_directory=str(chroma_path),
                embedding_function=self.embeddings,
            )
        else:
            if not docs_path.exists() or not any(docs_path.iterdir()):
                logger.warning("Aucun document trouvé dans %s", DOCS_DIR)
                return False

            logger.info("Chargement des documents depuis %s", DOCS_DIR)
            all_docs = []

            for pattern in ["**/*.txt", "**/*.md"]:
                loader = DirectoryLoader(
                    str(docs_path), glob=pattern,
                    loader_cls=TextLoader, show_progress=True,
                )
                try:
                    all_docs.extend(loader.load())
                except Exception as e:
                    logger.warning("Erreur loader %s : %s", pattern, e)

            for pdf_file in docs_path.rglob("*.pdf"):
                try:
                    pdf_loader = PyMuPDFLoader(str(pdf_file))
                    docs = pdf_loader.load()
                    all_docs.extend(docs)
                    logger.info("PDF chargé : %s (%d pages)", pdf_file.name, len(docs))
                except Exception as e:
                    logger.warning("Erreur PDF %s : %s", pdf_file.name, e)

            if not all_docs:
                logger.warning("Aucun fichier trouvé")
                return False

            logger.info("%d document(s) chargé(s), découpage...", len(all_docs))
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=1500,
                chunk_overlap=200,
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

        self.llm = ChatGroq(
            model=LLM_MODEL, api_key=GROQ_API_KEY,
            temperature=0.3, max_tokens=1024,
        )
        logger.info("Pipeline RAG initialisé avec succès.")
        return True

    def get_chain(self, user_id: int) -> ConversationalRetrievalChain:
        if user_id not in self.user_memories:
            self.user_memories[user_id] = ConversationBufferWindowMemory(
                k=MAX_HISTORY_TURNS, memory_key="chat_history",
                return_messages=True, output_key="answer",
            )
        return ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vectorstore.as_retriever(
                search_type="mmr", search_kwargs={"k": 5, "fetch_k": 15}),
            memory=self.user_memories[user_id],
            combine_docs_chain_kwargs={"prompt": PromptTemplate(
                input_variables=["context", "chat_history", "question"],
                template=SYSTEM_PROMPT)},
            condense_question_prompt=PromptTemplate(
                input_variables=["chat_history", "question"],
                template=CONDENSE_PROMPT),
            return_source_documents=True,
            verbose=False,
        )

    async def query(self, user_id: int, question: str) -> str:
        if not self.vectorstore or not self.llm:
            return "⚠️ La base de connaissances n'est pas encore chargée."
        try:
            result  = await asyncio.to_thread(self.get_chain(user_id).invoke, {"question": question})
            answer  = result.get("answer", "Je n'ai pas trouvé de réponse.")
            sources = list({
                Path(d.metadata.get("source","")).name
                for d in result.get("source_documents",[])
                if d.metadata.get("source")
            })
            if sources:
                answer += "\n\n📄 *Sources :* " + ", ".join(f"`{s}`" for s in sources)
            return answer
        except Exception as e:
            logger.error("Erreur RAG user %d : %s", user_id, e, exc_info=True)
            return f"❌ Erreur : {type(e).__name__} — {str(e)[:120]}"

bot = HermesRAGBot()

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"👋 Bonjour *{update.effective_user.first_name}* !\n\n"
        "Je suis *Hermes*, ton assistant RAG.\n\n"
        "📚 Pose-moi une question sur la base de connaissances.\n"
        "📖 Je peux répondre sur le livre *Kubernetes* du Pr\\. Grassa\\.\n"
        "🔄 /reset — effacer l'historique\n"
        "ℹ️ /status — état du système", parse_mode="Markdown")

async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot.user_memories.pop(update.effective_user.id, None)
    await update.message.reply_text("🗑️ Historique effacé !")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if bot.vectorstore:
        count = bot.vectorstore._collection.count()
        await update.message.reply_text(
            f"✅ *Système opérationnel*\n\n"
            f"🔢 Chunks indexés : *{count}*\n"
            f"🤖 Modèle : `{LLM_MODEL}`\n"
            f"🧠 Embeddings : `all-MiniLM-L6-v2`\n"
            f"🗂️ ChromaDB persistant",
            parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Base non initialisée.")

async def cmd_reload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("♻️ Rechargement en cours... (1-2 min pour le PDF)")
    shutil.rmtree(CHROMA_DIR, ignore_errors=True)
    bot.vectorstore = None
    success = await asyncio.to_thread(bot.initialize_rag)
    await update.message.reply_text("✅ Base rechargée !" if success else "❌ Échec — vérifie /docs.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    answer = await bot.query(update.effective_user.id, update.message.text)
    await update.message.reply_text(answer, parse_mode="Markdown")

def main():
    logger.info("Démarrage Hermes RAG Bot...")
    bot.initialize_rag()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("reset",  cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("reload", cmd_reload))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot en écoute...")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()
BOTEOF
