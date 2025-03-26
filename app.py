import streamlit as st
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage
from google.oauth2 import service_account
from googleapiclient.discovery import build
import json
import re
import os

# --- ページ設定 ---
st.set_page_config(page_title="RAGスカウト文ジェネレーター", layout="centered")
st.title("🧠 RAG × スカウトテンプレ自動生成")

# --- OpenAI APIキー（secretsから取得） ---
openai_api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")

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

# --- スカウト文生成プロンプト ---
def build_prompt(profile, rag_summary, jobs, sender):
    jobs_bullet = "\n".join([f"★{j}\n∟▶︎（この求人の魅力・強み・ポジション情報をWeb検索した前提でキャッチーに訴求）" for j in jobs if j])

    return f"""
以下の情報をもとに、過去のスカウト文の構造やトーンを踏襲しながら、候補者向けのスカウト文（件名＋本文）を生成してください。

【過去のスカウト文の特徴】
- 文頭にキャリアの次ステップを連想させる一文
- SIESTA代表によるシンプルな自己紹介（文頭のみ）
- スカウト送信の理由（経歴への共感、市場価値向上支援）
- 『上位1％』『完全支援』『年収UP実績』などの訴求要素を中盤に配置
- 魅力的な求人（釣り求人）をキャッチーに紹介し、ポジション年収を含める
- 文末は連絡を促す控えめかつ前向きな一文 + 担当者署名で締める

【候補者プロフィール】
{profile}

【釣り求人（キャッチーに訴求すること）】
{jobs_bullet}

【企業ナレッジ（RAG抽出内容）】
{rag_summary}

【テンプレート冒頭】
━━━━━━━━━━━━━━━━━━━━━
あなたの次のキャリアステップを、私たちと共に。
━━━━━━━━━━━━━━━━━━━━━

こんにちは、SIESTA代表の{sender}です。

【出力形式】
件名：◯◯◯◯
本文：

◯◯◯◯（1800文字前後）
"""

# --- メイン処理 ---
if generate_button and openai_api_key and candidate_profile:
    rag_summary = ""
    for keyword in [fishing_job_1, fishing_job_2, fishing_job_3]:
        if keyword:
            st.info(f"🔍 {keyword} の情報を取得中...")
            content = find_doc_content_by_keyword(keyword)
            if content:
                rag_summary += f"【{keyword}】\n{content}\n\n"

    if rag_summary:
        with st.expander("🔍 取得した企業ナレッジ（RAG）"):
            st.markdown(rag_summary)

    jobs = [fishing_job_1, fishing_job_2, fishing_job_3]

    st.info("🤖 GPTで文面生成中...")
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0.7, openai_api_key=openai_api_key)
    prompt = build_prompt(candidate_profile, rag_summary, jobs, contact_person)
    messages = [
        SystemMessage(content="あなたはハイクラス人材にスカウト文を作成するプロです。"),
        HumanMessage(content=prompt)
    ]
    response = llm(messages)

    st.success("✅ スカウト文が生成されました")
    st.markdown("""---""")
    st.markdown(response.content)

elif generate_button and not openai_api_key:
    st.error("OpenAI API Key を環境変数またはSecretsに設定してください")
