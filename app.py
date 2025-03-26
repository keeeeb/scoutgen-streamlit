import streamlit as st
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
import re

# --- ページ設定 ---
st.set_page_config(page_title="RAGスカウト文ジェネレーター", layout="centered")
st.title("🧠 RAG × スカウトテンプレ自動生成")

# --- OpenAI APIキー入力 ---
openai_api_key = st.text_input("🔑 OpenAI API Key", type="password")

# --- 入力欄 ---
candidate_profile = st.text_area("📄 候補者プロフィールを貼ってください")
fishing_company = st.text_input("🏢 釣り求人に含まれる企業名（例：キャディ）")
generate_button = st.button("🚀 スカウト文を生成")

# --- Google Driveからドキュメント取得関数 ---
def find_doc_content_by_keyword(keyword: str):
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    creds = service_account.Credentials.from_service_account_file(
        "service_account.json", scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)
    query = f"mimeType='application/vnd.google-apps.document' and name contains '{keyword}'"
    results = drive_service.files().list(q=query, fields="files(id, name)", pageSize=5).execute()
    files = results.get('files', [])

    if not files:
        return ""

    file_id = files[0]['id']
    doc_service = build('docs', 'v1', credentials=creds)
    doc = doc_service.documents().get(documentId=file_id).execute()

    content = ""
    for element in doc.get("body").get("content"):
        if "paragraph" in element:
            for elem in element["paragraph"].get("elements", []):
                text_run = elem.get("textRun")
                if text_run:
                    content += text_run.get("content")

    cleaned = re.sub(r'\n{2,}', '\n\n', content.strip())
    return cleaned

# --- スカウト文生成プロンプト ---
def build_prompt(profile, rag_context):
    return f"""
以下の候補者プロフィールをもとに、テンプレート文にパーソナライズ要素と企業訴求を馴染ませて、件名と本文を生成してください。

【候補者プロフィール】
{profile}

【参照情報（企業ナレッジ/RAG抽出）】
{rag_context}

【出力形式】
件名：◯◯◯◯（50文字以内）
本文：
◯◯◯◯（1800文字前後）
"""

# --- メイン処理 ---
if generate_button and openai_api_key and candidate_profile:
    rag_context = ""
    if fishing_company:
        st.info("🔍 Google Driveから企業ナレッジを取得中...")
        rag_context = find_doc_content_by_keyword(fishing_company)

    st.info("🤖 GPTで文面生成中...")
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=openai_api_key)
    prompt = build_prompt(candidate_profile, rag_context)
    messages = [SystemMessage(content="あなたはハイクラス人材にスカウト文を作成するプロです。"),
                HumanMessage(content=prompt)]
    response = llm(messages)

    st.success("✅ スカウト文が生成されました")
    st.markdown("""---""")
    st.markdown(response.content)

elif generate_button and not openai_api_key:
    st.error("OpenAI API Key を入力してください")
