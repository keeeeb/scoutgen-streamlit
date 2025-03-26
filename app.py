import streamlit as st
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import re
import os
import requests

# --- ページ設定 ---
st.set_page_config(page_title="RAGスカウト文ジェネレーター v3.5")
st.title("🧠 RAG × スカウトテンプレ自動生成 v3.5")

# --- APIキー ---
openai_api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
serpapi_key = os.environ.get("SERPAPI_KEY") or st.secrets.get("SERPAPI_KEY")

# --- 入力欄 ---
candidate_profile = st.text_area("📄 候補者プロフィールを貼ってください")
fishing_job_1 = st.text_input("🎯 釣り求人①（社名_求人タイトル）")
fishing_job_2 = st.text_input("🎯 釣り求人②（社名_求人タイトル）")
fishing_job_3 = st.text_input("🎯 釣り求人③（社名_求人タイトル）")
contact_person = st.text_input("🧑‍💼 スカウト送信者名（署名に表示）")
generate_button = st.button("🚀 スカウト文を生成")

# --- Google Driveからドキュメント取得関数 ---
def find_doc_content_by_keyword(keyword: str):
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    raw_json = st.secrets["SERVICE_ACCOUNT_JSON"]
    creds_dict = json.loads(raw_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=creds)
    query = f"mimeType='application/vnd.google-apps.document' and name contains '{keyword.split('_')[0]}'"
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

# --- SerpAPIから検索結果取得 ---
def get_serp_snippets(query):
    url = "https://serpapi.com/search.json"
    params = {
        "q": query,
        "hl": "ja",
        "gl": "jp",
        "api_key": serpapi_key
    }
    response = requests.get(url, params=params)
    data = response.json()
    snippets = []
    for res in data.get("organic_results", [])[:2]:
        title = res.get("title", "")
        snippet = res.get("snippet", "")
        snippets.append(f"【{title}】\n{snippet}")
    return "\n\n".join(snippets)

# --- プロンプト生成 ---
def build_prompt(profile, rag_summary, serp_summary, jobs, sender):
    jobs_bullet = "\n".join([f"★{j}" for j in jobs if j])

    return f"""
あなたは超一流のスカウトライターです。
以下の情報と構造を厳守し、候補者が「応募したくなる」「話を聞きたくなる」件名＋本文を生成してください。

【スカウト文構造（完全固定）】
1. 件名：具体性・限定性・戦略性・年収・業界名を含む50文字以内
2. 冒頭キャッチ："あなたの次のキャリアステップを、私たちと共に。"
3. 共感導入：候補者の◯◯経験に共感・期待（2文）
4. SIESTAの支援実績：上位1%、年収UP、具体事例（短くインパクトある表現）
5. 魅力訴求ブロック（3社分）:
  - 会社名
  - ポジション名
  - Web検索から得た特徴（強み、成長性、条件）
  - 「あなたの◯◯経験が活かされる」一言（プロファイルに合わせて）
6. 締め：カジュアル面談提案、安心感のあるトーン
7. 署名：文末にのみ表示（{sender}｜SIESTA代表）

【候補者プロフィール】
{profile}

【釣り求人（入力内容）】
{jobs_bullet}

【釣り求人の検索結果（SerpAPI）】
{serp_summary}

【Driveから取得した企業ナレッジ（RAG）】
{rag_summary}

【出力形式】
件名：◯◯◯◯（50文字以内）
本文：

━━━━━━━━━━━━━━━━━━━━━
あなたの次のキャリアステップを、私たちと共に。
━━━━━━━━━━━━━━━━━━━━━

◯◯◯◯（1800文字前後）

━━━━━━━━━━━━━━━━━━━━━
{sender}｜SIESTA代表
━━━━━━━━━━━━━━━━━━━━━
"""

# --- 実行ブロック ---
if generate_button and openai_api_key and candidate_profile:
    rag_summary = ""
    serp_summary = ""
    jobs = [fishing_job_1, fishing_job_2, fishing_job_3]

    for keyword in jobs:
        if keyword:
            st.info(f"🔍 {keyword} の企業ナレッジを取得中...")
            content = find_doc_content_by_keyword(keyword)
            if content:
                rag_summary += f"【{keyword}】\n{content}\n\n"
            st.info(f"🌐 {keyword} をWeb検索中...")
            serp = get_serp_snippets(keyword)
            if serp:
                serp_summary += f"【{keyword}】\n{serp}\n\n"

    if serp_summary:
        with st.expander("🌐 Web検索結果（SerpAPI）"):
            st.markdown(serp_summary)

    if rag_summary:
        with st.expander("📂 Driveナレッジ（RAG）"):
            st.markdown(rag_summary)

    st.info("🤖 GPTで文面生成中...")
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=openai_api_key, max_tokens=1800)
    prompt = build_prompt(candidate_profile, rag_summary, serp_summary, jobs, contact_person)
    messages = [
        SystemMessage(content="あなたはプロのスカウト文作成エージェントです。構成、トーン、訴求軸を厳密に守ってください。"),
        HumanMessage(content=prompt)
    ]
    response = llm(messages)

    st.success("✅ スカウト文が生成されました")
    st.markdown("""---""")
    st.markdown(response.content)

elif generate_button and not openai_api_key:
    st.error("OpenAI API Key を環境変数またはSecretsに設定してください")
